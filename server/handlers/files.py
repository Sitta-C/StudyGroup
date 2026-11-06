"""Chunked file upload/download over the same WebSocket/TLS socket as chat (CP08).

Upload: FILE_BEGIN -> FILE_CHUNK x N (ordered, Base64 of exactly 32 KiB except
the last) -> FILE_END. Bytes go to a server-named partial file; only after the
declared size and SHA-256 match is the file renamed to a server-generated
stored name and its message/attachment committed and published. A transfer
belongs to one connection and is removed on error, END, disconnect or idle
timeout. Download: FILE_GET reads one chunk at an offset after checking the
same room membership and join boundary as history.
"""

import base64
import binascii
from dataclasses import dataclass, field
import hashlib
import logging
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import threading
import time
import unicodedata

from server.database import add_file_message, transaction
from server.handlers.chat import ChatError, message_dto, positive_id, sized_response
from server.permissions import AccessDenied, message_recipient_ids, require_attachment, require_member
from shared.message_types import ErrorCode, EventType, RequestType
from shared.protocol import make_event

MAX_FILE_BYTES = 5 * 1024 * 1024
UPLOAD_CHUNK_BYTES = 32 * 1024
DOWNLOAD_CHUNK_BYTES = 128 * 1024
MAX_NAME_CHARS = 255
MAX_NAME_BYTES = 1020
MAX_TRANSFERS_PER_CONNECTION = 3
MAX_TRANSFERS = 32
TRANSFER_IDLE_SECONDS = 120.0
TRANSFER_MAX_SECONDS = 600.0  # A slow drip cannot hold a slot for hours.
FREE_SPACE_MARGIN = 64 * 1024 * 1024
_SHA256 = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_STORED_NAME = re.compile(r"[0-9a-f]{32}\Z", re.ASCII)
_PARTIAL_DIR = ".partial"

logger = logging.getLogger(__name__)


def _invalid(message):
    raise ChatError(ErrorCode.INVALID_INPUT, message)


def _fields(data, expected):
    if set(data) != set(expected):
        _invalid("Missing or unexpected request fields")


def display_name(value):
    """Validate the client's file name as a display label only.

    It is never used as a path: names with separators, traversal segments,
    control characters or reserved characters are rejected, not rewritten.
    """
    if not isinstance(value, str) or not value or len(value) > MAX_NAME_CHARS:
        _invalid("File name must be 1-255 characters")
    if len(value.encode("utf-8", "surrogatepass")) > MAX_NAME_BYTES or value != value.strip():
        _invalid("File name is too long or has surrounding spaces")
    if value in (".", "..") or any(ch in value for ch in '/\\:*?"<>|'):
        _invalid("File name must not contain a path or reserved characters")
    if any(unicodedata.category(ch) in ("Cc", "Cf", "Cs", "Zl", "Zp") for ch in value):
        _invalid("File name must not contain control characters")
    return value


@dataclass(eq=False)
class Transfer:
    id: str
    owner: object
    user_id: int
    room_id: int
    name: str
    size: int
    sha256: str
    path: Path
    handle: object
    last_activity: float
    started: float = 0.0
    received: int = 0
    next_index: int = 0
    hasher: object = field(default_factory=hashlib.sha256)
    lock: threading.Lock = field(default_factory=threading.Lock)
    closed: bool = False

    @property
    def chunks(self):
        return math.ceil(self.size / UPLOAD_CHUNK_BYTES)

    def discard(self):
        """Close and delete the partial file. Caller holds self.lock."""
        if self.closed:
            return
        self.closed = True
        try:
            self.handle.close()
        finally:
            self.path.unlink(missing_ok=True)


class FileHandlers:
    TYPES = frozenset((RequestType.FILE_BEGIN, RequestType.FILE_CHUNK, RequestType.FILE_END, RequestType.FILE_GET))

    def __init__(self, registry, uploads_dir, chat, *, clock=time.monotonic,
                 idle_timeout=TRANSFER_IDLE_SECONDS, max_lifetime=TRANSFER_MAX_SECONDS):
        self.registry = registry
        self.uploads_dir = Path(uploads_dir)
        self.partial_dir = self.uploads_dir / _PARTIAL_DIR
        self.chat = chat
        self.clock = clock
        self.idle_timeout = idle_timeout
        self.max_lifetime = max_lifetime
        self._lock = threading.Lock()
        self._transfers = {}

    def prepare(self, database=None):
        """Create upload directories and remove files left by a crash.

        Partial uploads never published. A stored file with no attachment row
        means the server stopped between the rename and the commit.
        """
        self.partial_dir.mkdir(parents=True, exist_ok=True)
        for leftover in self.partial_dir.glob("*.part"):
            leftover.unlink(missing_ok=True)
        if database is None:
            return
        with database.connect() as db:
            known = {row[0] for row in db.execute("SELECT stored_name FROM attachments")}
        for stored in self.uploads_dir.iterdir():
            if stored.is_file() and _STORED_NAME.fullmatch(stored.name) and stored.name not in known:
                stored.unlink(missing_ok=True)

    # Transfer registry -------------------------------------------------

    def active_transfers(self):
        with self._lock:
            return len(self._transfers)

    def _take(self, transfer_id, connection):
        """Remove and return the caller's transfer, or fail without detail."""
        with self._lock:
            transfer = self._transfers.get(transfer_id) if isinstance(transfer_id, str) else None
            if transfer is None or transfer.owner is not connection or transfer.user_id != connection.user["id"]:
                transfer = None
            else:
                del self._transfers[transfer_id]
        if transfer is None:
            _invalid("Unknown or expired file transfer")
        return transfer

    def _find(self, transfer_id, connection):
        with self._lock:
            transfer = self._transfers.get(transfer_id) if isinstance(transfer_id, str) else None
            if transfer is None or transfer.owner is not connection or transfer.user_id != connection.user["id"]:
                _invalid("Unknown or expired file transfer")
            return transfer

    def _abort(self, transfer):
        with self._lock:
            if self._transfers.get(transfer.id) is transfer:
                del self._transfers[transfer.id]
        transfer.discard()

    def _expired(self, transfer, now):
        return (now - transfer.last_activity >= self.idle_timeout
                or now - transfer.started >= self.max_lifetime)

    def _sweep(self):
        now = self.clock()
        with self._lock:
            stale = [t for t in self._transfers.values() if self._expired(t, now)]
        for transfer in stale:
            # Skip a transfer whose owner is writing right now; it is not idle.
            if transfer.lock.acquire(blocking=False):
                try:
                    # A chunk may have landed since the list was built.
                    if not transfer.closed and self._expired(transfer, self.clock()):
                        self._abort(transfer)
                finally:
                    transfer.lock.release()

    def connection_closed(self, connection):
        """Called by the connection worker after logout/EOF/error cleanup."""
        with self._lock:
            owned = [t for t in self._transfers.values() if t.owner is connection]
            for transfer in owned:
                del self._transfers[transfer.id]
        for transfer in owned:
            with transfer.lock:
                transfer.discard()

    # Requests ----------------------------------------------------------

    def handle(self, connection, db, request):
        kind, data, request_id = request["type"], request["data"], request["id"]
        self._sweep()  # Expire abandoned transfers on any file activity.
        if kind == RequestType.FILE_BEGIN:
            self._begin(connection, db, request_id, data)
        elif kind == RequestType.FILE_CHUNK:
            self._chunk(connection, request_id, data)
        elif kind == RequestType.FILE_END:
            self._end(connection, db, request_id, data)
        else:
            self._get(connection, db, request_id, data)

    def _begin(self, connection, db, request_id, data):
        _fields(data, ("room_id", "name", "size", "sha256"))
        room_id = positive_id(data["room_id"])
        name = display_name(data["name"])
        size = data["size"]
        if type(size) is not int or not 0 <= size <= MAX_FILE_BYTES:
            _invalid("File size must be between 0 and 5 MiB")
        digest = data["sha256"]
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            _invalid("sha256 must be 64 lowercase hexadecimal characters")
        require_member(db, connection.user["id"], room_id)
        try:
            free = shutil.disk_usage(self.uploads_dir).free
        except OSError:
            free = 0
        if free < size + FREE_SPACE_MARGIN:
            raise ChatError(ErrorCode.RATE_LIMITED, "Server storage is full; try later")
        with self._lock:
            owned = sum(1 for t in self._transfers.values() if t.owner is connection)
            if owned >= MAX_TRANSFERS_PER_CONNECTION or len(self._transfers) >= MAX_TRANSFERS:
                raise ChatError(ErrorCode.RATE_LIMITED, "Too many file transfers in progress")
            transfer_id = secrets.token_hex(16)
            path = self.partial_dir / f"{transfer_id}.part"
            # O_EXCL + server-generated name: nothing from the client reaches the path.
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
            transfer = Transfer(transfer_id, connection, connection.user["id"], room_id, name, size,
                                digest, path, os.fdopen(descriptor, "wb"), self.clock(), self.clock())
            self._transfers[transfer_id] = transfer
        connection.enqueue(sized_response(request_id, {
            "transfer_id": transfer_id, "chunk_size": UPLOAD_CHUNK_BYTES, "chunks": transfer.chunks,
        }))

    def _chunk(self, connection, request_id, data):
        _fields(data, ("transfer_id", "index", "data"))
        transfer = self._find(data["transfer_id"], connection)
        with transfer.lock:
            if transfer.closed:
                _invalid("Unknown or expired file transfer")
            try:
                index, payload = data["index"], data["data"]
                if type(index) is not int or index != transfer.next_index:
                    _invalid("File chunks must arrive in order")
                expected = min(UPLOAD_CHUNK_BYTES, transfer.size - transfer.received)
                if expected <= 0:
                    _invalid("File already has all declared bytes")
                if not isinstance(payload, str) or len(payload) != 4 * math.ceil(expected / 3):
                    _invalid("Chunk has the wrong length")
                try:
                    chunk = base64.b64decode(payload, validate=True)
                except (binascii.Error, ValueError):
                    _invalid("Chunk is not valid Base64")
                # Count real decoded bytes, never the client's claim.
                if len(chunk) != expected:
                    _invalid("Chunk has the wrong length")
                transfer.handle.write(chunk)
            except ChatError:
                self._abort(transfer)
                raise
            except OSError:
                self._abort(transfer)
                logger.error("Could not store an uploaded chunk")
                raise ChatError(ErrorCode.INTERNAL_ERROR, "Could not store the file") from None
            transfer.hasher.update(chunk)
            transfer.received += len(chunk)
            transfer.next_index += 1
            transfer.last_activity = self.clock()
            received = transfer.received
        connection.enqueue(sized_response(request_id, {"received": received}))

    def _end(self, connection, db, request_id, data):
        _fields(data, ("transfer_id",))
        transfer = self._take(data["transfer_id"], connection)
        final, committed = None, False
        with transfer.lock:
            try:
                if transfer.closed:
                    _invalid("Unknown or expired file transfer")
                if transfer.received != transfer.size:
                    _invalid("File is incomplete")
                if transfer.hasher.hexdigest() != transfer.sha256:
                    _invalid("File hash does not match")
                transfer.handle.flush()
                os.fsync(transfer.handle.fileno())
                transfer.handle.close()
                transfer.closed = True
                stored_name = secrets.token_hex(16)
                final = self.uploads_dir / stored_name
                os.replace(transfer.path, final)
                self._sync_directory()
                with self.chat.publish_lock:
                    with transaction(db):
                        row = add_file_message(
                            db, transfer.user_id, transfer.room_id, stored_name=stored_name,
                            original_name=transfer.name, size_bytes=transfer.size, sha256=transfer.sha256,
                        )
                        recipients = message_recipient_ids(db, row["id"])
                    committed = True
                    message = message_dto(row)
                    connection.enqueue(sized_response(request_id, {"message": message}))
                    self.registry.publish(make_event(EventType.MESSAGE_NEW, message), user_ids=recipients)
            except BaseException as error:
                # The partial file is gone once renamed; unlink is then a no-op.
                transfer.closed = True
                try:
                    transfer.handle.close()
                finally:
                    transfer.path.unlink(missing_ok=True)
                if final is not None and not committed:
                    final.unlink(missing_ok=True)
                # AccessDenied is a PermissionError (an OSError) but means FORBIDDEN.
                if isinstance(error, OSError) and not isinstance(error, AccessDenied):
                    logger.error("Could not publish an uploaded file")
                    raise ChatError(ErrorCode.INTERNAL_ERROR, "Could not store the file") from None
                raise

    def _sync_directory(self):
        """Make the rename durable before the attachment row is committed."""
        try:
            descriptor = os.open(self.uploads_dir, os.O_RDONLY)
        except OSError:
            return  # Not supported on every platform; the rename itself succeeded.
        try:
            os.fsync(descriptor)
        except OSError:
            pass
        finally:
            os.close(descriptor)

    def _get(self, connection, db, request_id, data):
        if set(data) - {"attachment_id", "offset"} or "attachment_id" not in data:
            _invalid("Missing or unexpected request fields")
        attachment_id = positive_id(data["attachment_id"])
        offset = data.get("offset", 0)
        row = require_attachment(db, connection.user["id"], attachment_id)
        size = row["size_bytes"]
        if type(offset) is not int or not 0 <= offset <= size or (offset == size and size):
            _invalid("offset is outside the file")
        stored = row["stored_name"]
        path = self.uploads_dir / stored
        if not _STORED_NAME.fullmatch(stored) or path.parent != self.uploads_dir:
            raise ChatError(ErrorCode.NOT_FOUND, "File content is unavailable")
        try:
            with open(path, "rb") as handle:
                handle.seek(offset)
                chunk = handle.read(min(DOWNLOAD_CHUNK_BYTES, size - offset))
        except OSError:
            raise ChatError(ErrorCode.NOT_FOUND, "File content is unavailable") from None
        if len(chunk) != min(DOWNLOAD_CHUNK_BYTES, size - offset):
            raise ChatError(ErrorCode.NOT_FOUND, "File content is unavailable")
        connection.enqueue(sized_response(request_id, {
            "attachment_id": attachment_id, "name": row["original_name"], "size": size,
            "sha256": row["sha256"], "offset": offset, "data": base64.b64encode(chunk).decode("ascii"),
            "done": offset + len(chunk) >= size,
        }))
