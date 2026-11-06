"""Authenticated room commands and committed, permission-scoped live events."""

import threading

from server.database import (
    add_text_message,
    create_group,
    join_group,
    open_private_room,
    transaction,
)
from server.handlers.auth import fields
from server.permissions import message_recipient_ids, require_user
from shared.message_types import ErrorCode, EventType, RequestType
from shared.protocol import encode_packet, make_event, make_response
from shared.validation import ProtocolError

MAX_GROUP_NAME_CHARS = 100
MAX_TEXT_CHARS = 4000
MAX_TEXT_BYTES = 16000
MAX_SQLITE_ID = 2**63 - 1


class ChatError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def positive_id(value):
    if type(value) is not int or not 1 <= value <= MAX_SQLITE_ID:
        raise ChatError(ErrorCode.INVALID_INPUT, "ID must be a positive 64-bit integer")
    return value


def _text(value, *, group_name=False):
    max_chars = MAX_GROUP_NAME_CHARS if group_name else MAX_TEXT_CHARS
    if (not isinstance(value, str) or not value.strip() or "\x00" in value
            or len(value) > max_chars or len(value.encode("utf-8")) > MAX_TEXT_BYTES):
        raise ChatError(ErrorCode.INVALID_INPUT, "Text is empty, invalid or too long")
    return value.strip() if group_name else value


def _room(db, room_id):
    row = db.execute(
        "SELECT id, kind, name, created_by, created_at FROM rooms WHERE id = ?", (room_id,),
    ).fetchone()
    members = db.execute(
        """SELECT u.id, u.username, rm.joined_at FROM room_members AS rm
           JOIN users AS u ON u.id = rm.user_id WHERE rm.room_id = ? ORDER BY u.id""",
        (room_id,),
    ).fetchall()
    return dict(row) | {"members": [dict(member) for member in members]}


def message_dto(row):
    """Wire Message for responses, history and MESSAGE_NEW (text shape unchanged).

    File messages carry text null plus attachment metadata; the server-side
    stored name never leaves the server.
    """
    message = {"message_id": row["id"], "room_id": row["room_id"], "sender_id": row["sender_id"],
               "text": row["text"], "created_at": row["created_at"]}
    if row["kind"] == "file":
        message["attachment"] = {"id": row["attachment_id"], "name": row["attachment_name"],
                                 "size": row["attachment_size"], "sha256": row["attachment_sha256"]}
    return message


def room_dto(db, room_id):
    return _room(db, room_id)


def sized_response(request_id, result):
    """A response that must fit one frame; clients retry with a smaller page."""
    return _response(request_id, result)


def _response(request_id, result):
    response = make_response(request_id, result)
    try:
        encode_packet(response)
    except ProtocolError as error:
        raise ChatError(error.code, "Room data exceeds frame limit; request a smaller page") from None
    return response


class ChatHandlers:
    TYPES = frozenset((RequestType.PRIVATE_ROOM_OPEN, RequestType.GROUP_CREATE,
                       RequestType.GROUP_LIST, RequestType.GROUP_JOIN, RequestType.MESSAGE_SEND))

    def __init__(self, registry):
        self.registry = registry
        # Serialize commit -> enqueue, including join boundaries. No socket I/O
        # occurs under this lock. Each worker still owns its SQLite connection.
        # FileHandlers publishes file messages under this same lock.
        self.publish_lock = threading.Lock()

    def handle(self, connection, db, request):
        with self.publish_lock:
            self._handle(connection, db, request)

    def _handle(self, connection, db, request):
        kind, data, request_id = request["type"], request["data"], request["id"]
        actor = connection.user["id"]
        if kind == RequestType.GROUP_LIST:
            if set(data) - {"after_id", "limit"}:
                raise ChatError(ErrorCode.INVALID_INPUT, "Unexpected request fields")
            after_id, limit = data.get("after_id", 0), data.get("limit", 50)
            if type(after_id) is not int or not 0 <= after_id <= MAX_SQLITE_ID:
                raise ChatError(ErrorCode.INVALID_INPUT, "after_id must be a nonnegative 64-bit integer")
            if type(limit) is not int or not 1 <= limit <= 100:
                raise ChatError(ErrorCode.INVALID_INPUT, "limit must be an integer between 1 and 100")
            require_user(db, actor)
            rows = db.execute(
                "SELECT id FROM rooms WHERE kind = 'group' AND id > ? ORDER BY id LIMIT ?",
                (after_id, limit + 1),
            ).fetchall()
            groups = [_room(db, row["id"]) for row in rows[:limit]]
            response = _response(request_id, {
                "groups": groups, "next_after_id": groups[-1]["id"] if len(rows) > limit else None,
            })
            connection.enqueue(response)
            return
        if kind == RequestType.PRIVATE_ROOM_OPEN:
            fields(data, ("peer_id",))
            peer_id = positive_id(data["peer_id"])
            if peer_id == actor:
                raise ChatError(ErrorCode.INVALID_INPUT, "A private room needs two different users")
            room = open_private_room(db, actor, peer_id)
            connection.enqueue(make_response(request_id, {"room": _room(db, room["id"])}))
            return
        if kind == RequestType.GROUP_CREATE:
            fields(data, ("name",))
            name = _text(data["name"], group_name=True)
            with transaction(db):
                room = create_group(db, actor, name)
                response = _response(request_id, {"room": _room(db, room["id"])})
            connection.enqueue(response)
            self.registry.publish(make_event(EventType.GROUPS_UPDATED, {"room_id": room["id"]}))
            return
        if kind == RequestType.GROUP_JOIN:
            fields(data, ("room_id",))
            room_id = positive_id(data["room_id"])
            with transaction(db):
                existed = db.execute(
                    "SELECT 1 FROM room_members WHERE room_id = ? AND user_id = ?", (room_id, actor),
                ).fetchone()
                join_group(db, actor, room_id)
                response = _response(request_id, {"room": _room(db, room_id)})
            connection.enqueue(response)
            if not existed:
                self.registry.publish(make_event(EventType.GROUPS_UPDATED, {"room_id": room_id}))
            return
        fields(data, ("room_id", "text"))
        room_id, text = positive_id(data["room_id"]), _text(data["text"])
        with transaction(db):
            row = add_text_message(db, actor, room_id, text)
            message = message_dto(row)
            # Reuse the history/file visibility predicate, including the
            # private pair guard and the member's join boundary.
            recipients = message_recipient_ids(db, row["id"])
        connection.enqueue(make_response(request_id, {"message": message}))
        self.registry.publish(make_event(EventType.MESSAGE_NEW, message), user_ids=recipients)
