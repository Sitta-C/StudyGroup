"""AI_SUMMARIZE (CP09): group-only, member-only, at most the 50 latest visible messages.

The connection worker validates and reads the permitted messages, then hands
the slow provider call to a small bounded worker pool so chat on this and
other connections keeps flowing. The worker re-checks access with its own
SQLite connection before answering only the requesting connection; results
are never published to the room or any other user.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
import logging
import threading
import time

from server.ai_service import SYSTEM_PROMPT, AIUnavailable, Line, build_prompt, parse_summary
from server.database import get_messages
from server.handlers.chat import ChatError, positive_id, sized_response
from server.permissions import AccessDenied, require_member, require_message
from shared.message_types import ErrorCode, RequestType
from shared.protocol import make_error

MAX_INPUT_MESSAGES = 50
AI_WORKERS = 2
MAX_PENDING = 8
COOLDOWN_SECONDS = 10.0

logger = logging.getLogger(__name__)


class AIHandlers:
    TYPES = frozenset((RequestType.AI_SUMMARIZE,))

    def __init__(self, database, provider, *, workers=AI_WORKERS, cooldown=COOLDOWN_SECONDS,
                 clock=time.monotonic):
        self.database = database
        self.provider = provider
        self.cooldown = cooldown
        self.clock = clock
        self._lock = threading.Lock()
        self._busy = set()      # user IDs with a summary in progress
        self._last = {}         # user ID -> monotonic time of the last accepted request
        self._pending = 0
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="studygroup-ai")

    def shutdown(self):
        self._pool.shutdown(wait=False, cancel_futures=True)

    def handle(self, connection, db, request):
        data, request_id = request["data"], request["id"]
        if set(data) != {"room_id"}:
            raise ChatError(ErrorCode.INVALID_INPUT, "Missing or unexpected request fields")
        room_id = positive_id(data["room_id"])
        actor = connection.user["id"]
        member = require_member(db, actor, room_id)
        if member["kind"] != "group":
            raise AccessDenied()  # Summaries are for group rooms only.
        if self.provider is None:
            raise ChatError(ErrorCode.AI_UNAVAILABLE, "AI summary is not configured on this server")
        rows = get_messages(db, actor, room_id, limit=MAX_INPUT_MESSAGES)  # Oldest first.
        room = db.execute("SELECT name FROM rooms WHERE id = ?", (room_id,)).fetchone()
        names = {row["id"]: row["username"] for row in db.execute(
            "SELECT u.id, u.username FROM room_members AS rm JOIN users AS u ON u.id = rm.user_id"
            " WHERE rm.room_id = ?", (room_id,))}
        lines = [Line(names.get(row["sender_id"], f"user{row['sender_id']}"), row["created_at"],
                      row["text"] if row["kind"] == "text" else f"[ส่งไฟล์: {row['attachment_name']}]")
                 for row in rows]
        meta = {"room_id": room_id, "message_count": len(rows),
                "first_message_id": rows[0]["id"] if rows else None,
                "last_message_id": rows[-1]["id"] if rows else None,
                "provider": self.provider.name, "model": self.provider.model,
                "mock": self.provider.name == "mock"}
        if not rows:
            connection.enqueue(sized_response(request_id, meta | {
                "generated_at": _now(), "summary": {"topics": [], "agreements": [], "tasks": [], "deadlines": []}}))
            return
        now = self.clock()
        with self._lock:
            if actor in self._busy:
                raise ChatError(ErrorCode.RATE_LIMITED, "A summary is already in progress")
            if now - self._last.get(actor, -self.cooldown) < self.cooldown:
                raise ChatError(ErrorCode.RATE_LIMITED, "Please wait before requesting another summary")
            if self._pending >= MAX_PENDING:
                raise ChatError(ErrorCode.RATE_LIMITED, "AI is busy; try again shortly")
            self._busy.add(actor)
            self._last[actor] = now
            self._pending += 1
        try:
            self._pool.submit(self._run, connection, request_id, actor, room["name"], lines, meta)
        except RuntimeError:  # Pool shut down while the server stops.
            self._release(actor)
            raise ChatError(ErrorCode.AI_UNAVAILABLE, "AI summary is not available right now") from None

    def _release(self, actor):
        with self._lock:
            self._busy.discard(actor)
            self._pending -= 1

    def _run(self, connection, request_id, actor, room_name, lines, meta):
        try:
            try:
                raw = self.provider.complete(SYSTEM_PROMPT, build_prompt(room_name, lines))
                summary = parse_summary(raw, lines)
                # Access is checked again with this worker's own connection.
                with self.database.connect() as db:
                    require_member(db, actor, meta["room_id"])
                    require_message(db, actor, meta["last_message_id"])
                packet = sized_response(request_id, meta | {"generated_at": _now(), "summary": summary})
            except AIUnavailable as error:
                packet = make_error(request_id, ErrorCode.AI_UNAVAILABLE, str(error))
            except AccessDenied:
                packet = make_error(request_id, ErrorCode.FORBIDDEN, "Access to this content is forbidden")
            except ChatError as error:
                packet = make_error(request_id, error.code, str(error))
            except Exception:
                logger.error("AI summary failed")  # No prompt, key or exception text in logs.
                packet = make_error(request_id, ErrorCode.AI_UNAVAILABLE, "AI summary failed")
            user = connection.user
            # Answer only the same signed-in user on the same connection.
            if user is not None and user["id"] == actor:
                connection.enqueue(packet)
        finally:
            self._release(actor)


def _now():
    now = datetime.now(UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
