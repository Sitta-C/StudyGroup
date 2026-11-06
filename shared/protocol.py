"""Blocking length-prefixed JSON transport, usable with TCP or TLS sockets.

One PacketConnection per socket, one reader, all writers using send_packet().
The caller owns timeouts and socket cleanup; discard the connection after any
receive error or failed sendall because the stream may be partway through a frame.
"""

import json
import struct
import threading
from uuid import uuid4

from shared.message_types import (
    PROTOCOL_VERSION,
    RESPONSE_TYPE,
    ErrorCode,
    EventType,
    RequestType,
)
from shared.validation import ProtocolError, validate_packet

HEADER = struct.Struct("!I")
MAX_FRAME_BYTES = 1024 * 1024  # JSON body only, measured after UTF-8 encoding.


class IncompleteFrameError(EOFError):
    """EOF after a frame has started; never a successful disconnect."""

    def __init__(self, expected: int, received: int):
        self.expected = expected
        self.received = received
        super().__init__(f"Unexpected EOF: expected {expected} bytes, received {received}")


def recv_exact(sock, size: int, *, allow_eof: bool = False) -> bytes | None:
    """Read exactly size bytes; None is allowed only for EOF before any bytes.

    recv_packet allows this only at the start of a new header. A missing body,
    including zero body bytes after a complete header, is truncated, not clean EOF.
    """
    if type(size) is not int or not 0 <= size <= MAX_FRAME_BYTES:
        raise ValueError("Read size must be between 0 and MAX_FRAME_BYTES")
    result = bytearray()
    while len(result) < size:
        chunk = sock.recv(size - len(result))
        if not chunk:
            if allow_eof and not result:
                return None
            raise IncompleteFrameError(size, len(result))
        result.extend(chunk)
    return bytes(result)


def _reject_constant(_value):
    raise ValueError("Nonstandard JSON constant")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def encode_packet(packet: dict) -> bytes:
    """Validate and encode one frame. Never write any bytes on validation errors."""
    validate_packet(packet)
    try:
        body = json.dumps(
            packet, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        ).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ProtocolError(ErrorCode.INVALID_JSON, "Packet cannot be encoded as JSON") from None
    if len(body) > MAX_FRAME_BYTES:
        raise ProtocolError(ErrorCode.FRAME_TOO_LARGE, "JSON body exceeds 1 MiB")
    return HEADER.pack(len(body)) + body


def recv_packet(sock) -> dict | None:
    """Read one validated packet, or None on EOF between complete frames."""
    header = recv_exact(sock, HEADER.size, allow_eof=True)
    if header is None:
        return None
    size = HEADER.unpack(header)[0]
    if size == 0:
        raise ProtocolError(ErrorCode.INVALID_FRAME, "JSON body cannot be empty")
    if size > MAX_FRAME_BYTES:
        # No body read or allocation based on the untrusted length happens here.
        raise ProtocolError(ErrorCode.FRAME_TOO_LARGE, "JSON body exceeds 1 MiB")
    body = recv_exact(sock, size)
    try:
        packet = json.loads(
            body.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (ValueError, UnicodeError, RecursionError):
        raise ProtocolError(ErrorCode.INVALID_JSON, "Body must be valid UTF-8 JSON") from None
    return validate_packet(packet)


class PacketConnection:
    """The shared writer for a socket; never create competing wrappers for it."""

    def __init__(self, sock):
        self.socket = sock
        self._write_lock = threading.Lock()
        self._write_failed = False

    def send_packet(self, packet: dict) -> None:
        frame = encode_packet(packet)
        with self._write_lock:
            if self._write_failed:
                raise ConnectionError("A previous send failed; discard this connection")
            try:
                self.socket.sendall(frame)
            except OSError:
                # sendall cannot tell us how many bytes made it onto the wire.
                self._write_failed = True
                raise

    def recv_packet(self) -> dict | None:
        return recv_packet(self.socket)


def make_request(kind: RequestType, data: dict, *, request_id: str | None = None) -> dict:
    if kind not in RequestType:
        raise ValueError("Expected a request type")
    return validate_packet({
        "v": PROTOCOL_VERSION,
        "id": uuid4().hex if request_id is None else request_id,
        "type": str(kind),
        "data": data,
    })


def make_response(request_id: str, result: dict) -> dict:
    return validate_packet({
        "v": PROTOCOL_VERSION, "id": request_id, "type": RESPONSE_TYPE,
        "data": {"ok": True, "result": result},
    })


def make_error(request_id: str, code: ErrorCode, message: str) -> dict:
    return validate_packet({
        "v": PROTOCOL_VERSION, "id": request_id, "type": RESPONSE_TYPE,
        "data": {"ok": False, "error": {"code": code, "message": message}},
    })


def make_event(kind: EventType, data: dict) -> dict:
    if kind not in EventType:
        raise ValueError("Expected an event type")
    return validate_packet({"v": PROTOCOL_VERSION, "type": str(kind), "data": data})
