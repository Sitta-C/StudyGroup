"""Persistent history, keyword/date search and the caller's private rooms (CP07).

Every read goes through server.database.search_messages, which applies the
shared membership predicate and join boundary from server.permissions.
Pagination is keyset by message ID, so messages committed between page loads
(always larger IDs) cannot shift, skip or duplicate an older page.
"""

from datetime import UTC, datetime, timedelta

from server.database import list_private_rooms, search_messages
from server.handlers.chat import ChatError, MAX_SQLITE_ID, message_dto, positive_id, room_dto, sized_response
from shared.message_types import ErrorCode, RequestType

DEFAULT_PAGE = 50
MAX_PAGE = 100
MAX_QUERY_CHARS = 200
MAX_TIMESTAMP_CHARS = 40
_MIN_YEAR, _MAX_YEAR = 2000, 9998


def _invalid(message):
    raise ChatError(ErrorCode.INVALID_INPUT, message)


def _only(data, allowed, required=()):
    if set(data) - set(allowed) or set(required) - set(data):
        _invalid("Missing or unexpected request fields")


def _limit(data):
    limit = data.get("limit", DEFAULT_PAGE)
    if type(limit) is not int or not 1 <= limit <= MAX_PAGE:
        _invalid("limit must be an integer between 1 and 100")
    return limit


def _before(data):
    return positive_id(data["before_id"]) if "before_id" in data else None


def utc_bound(value, field):
    """An ISO 8601 instant with an explicit offset -> stored UTC text format.

    Clients convert the user's local calendar dates to instants; the server
    still normalises any offset to UTC before comparing with created_at.
    Sub-millisecond input is rounded up, which keeps since-inclusive and
    until-exclusive exact against millisecond timestamps.
    """
    if not isinstance(value, str) or not 10 <= len(value) <= MAX_TIMESTAMP_CHARS:
        _invalid(f"{field} must be an ISO 8601 timestamp with a UTC offset")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        _invalid(f"{field} must be an ISO 8601 timestamp with a UTC offset")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _invalid(f"{field} must include a UTC offset such as Z or +07:00")
    if not _MIN_YEAR <= parsed.year <= _MAX_YEAR:
        _invalid(f"{field} is outside the supported date range")
    parsed = parsed.astimezone(UTC)
    if parsed.microsecond % 1000:
        parsed += timedelta(microseconds=1000 - parsed.microsecond % 1000)
    if not _MIN_YEAR <= parsed.year <= _MAX_YEAR:
        _invalid(f"{field} is outside the supported date range")
    return parsed.strftime("%Y-%m-%dT%H:%M:%S.") + f"{parsed.microsecond // 1000:03d}Z"


def _page(rows, limit):
    """rows were fetched with limit + 1, newest first."""
    page = rows[:limit]
    return page, (page[-1]["id"] if len(rows) > limit else None)


class HistoryHandlers:
    TYPES = frozenset((RequestType.HISTORY_GET, RequestType.HISTORY_SEARCH, RequestType.PRIVATE_ROOM_LIST))

    def handle(self, connection, db, request):
        kind, data, request_id = request["type"], request["data"], request["id"]
        actor = connection.user["id"]
        if kind == RequestType.PRIVATE_ROOM_LIST:
            _only(data, ("after_id", "limit"))
            after_id = data.get("after_id", 0)
            if type(after_id) is not int or not 0 <= after_id <= MAX_SQLITE_ID:
                _invalid("after_id must be a nonnegative 64-bit integer")
            limit = _limit(data)
            rows = list_private_rooms(db, actor, after_id=after_id, limit=limit + 1)
            rooms = [room_dto(db, row["id"]) for row in rows[:limit]]
            connection.enqueue(sized_response(request_id, {
                "rooms": rooms, "next_after_id": rooms[-1]["id"] if len(rows) > limit else None,
            }))
            return
        if kind == RequestType.HISTORY_GET:
            _only(data, ("room_id", "before_id", "limit"), ("room_id",))
            room_id, before_id, limit = positive_id(data["room_id"]), _before(data), _limit(data)
            rows = search_messages(db, actor, room_id, before_id=before_id, limit=limit + 1)
            page, next_before = _page(rows, limit)
            # History pages are oldest first so they can be appended to a transcript.
            connection.enqueue(sized_response(request_id, {
                "messages": [message_dto(row) for row in reversed(page)], "next_before_id": next_before,
            }))
            return
        _only(data, ("room_id", "query", "from", "to", "kind", "before_id", "limit"), ("room_id",))
        room_id, before_id, limit = positive_id(data["room_id"]), _before(data), _limit(data)
        query = data.get("query")
        if query is not None:
            if (not isinstance(query, str) or "\x00" in query or not query.strip()
                    or len(query) > MAX_QUERY_CHARS):
                _invalid("query must be 1-200 characters and not blank")
            query = query.strip()
        since = utc_bound(data["from"], "from") if "from" in data else None
        until = utc_bound(data["to"], "to") if "to" in data else None
        if since is not None and until is not None and since >= until:
            _invalid("from must be earlier than to")
        message_kind = data.get("kind")
        if message_kind is not None and message_kind not in ("text", "file"):
            _invalid("kind must be text or file")
        if query is None and since is None and until is None and message_kind is None:
            _invalid("Search needs a query, a date range or a kind")
        rows = search_messages(db, actor, room_id, query=query, since=since, until=until,
                               kind=message_kind, before_id=before_id, limit=limit + 1)
        page, next_before = _page(rows, limit)
        # Search results are newest first, like a results list.
        connection.enqueue(sized_response(request_id, {
            "messages": [message_dto(row) for row in page], "next_before_id": next_before,
        }))
