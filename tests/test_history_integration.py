"""CP07 history/search over real WebSocket connections and temporary SQLite."""

from pathlib import Path
import sqlite3

import pytest

from server.web import WebServer
from server.web_config import WebConfig
from server.handlers.history import utc_bound
from server.handlers.chat import ChatError
from shared.message_types import ErrorCode as E, RequestType as R
from web_peer import ORIGIN, connect_peer


@pytest.fixture
def servers(tmp_path):
    started = []
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html><title>StudyGroup</title>")

    def start(data="data"):
        server = WebServer(WebConfig("127.0.0.1", 0, tmp_path / data, static, (ORIGIN,))).start()
        started.append(server)
        return server

    def stop(server):
        server.stop()
        started.remove(server)

    start.stop = stop
    yield start
    for server in reversed(started):
        server.stop()


@pytest.fixture
def server(servers):
    return servers()


def ids(messages):
    return [message["message_id"] for message in messages]


def set_time(server, message_id, created_at):
    db = sqlite3.connect(server.config.database_path)
    try:
        with db:
            db.execute("UPDATE messages SET created_at = ? WHERE id = ?", (created_at, message_id))
    finally:
        db.close()


def test_history_survives_client_and_server_restart_with_private_rooms(servers):
    first = servers()
    with connect_peer(first) as alice, connect_peer(first) as bob:
        alice.register("Alice"), bob.register("Bob")
        private = alice.ok(R.PRIVATE_ROOM_OPEN, {"peer_id": bob.user["id"]})["room"]
        group = alice.ok(R.GROUP_CREATE, {"name": "ทีม Network"})["room"]
        sent = [alice.say(private["id"], "ส่วนตัว 👋\nบรรทัดสอง"), bob.say(private["id"], "ตอบกลับ"),
                alice.say(group["id"], "ประชุมสองทุ่ม")]
    servers.stop(first)
    second = servers()  # Same data directory: a new process would see the same file.
    with connect_peer(second) as alice:
        alice.login("Alice")
        listed = alice.ok(R.PRIVATE_ROOM_LIST)
        assert [room["id"] for room in listed["rooms"]] == [private["id"]] and listed["next_after_id"] is None
        assert {m["username"] for m in listed["rooms"][0]["members"]} == {"Alice", "Bob"}  # Bob is offline.
        history = alice.ok(R.HISTORY_GET, {"room_id": private["id"]})
        assert history == {"messages": sent[:2], "next_before_id": None}
        assert alice.ok(R.HISTORY_GET, {"room_id": group["id"]})["messages"] == sent[2:]


def test_private_room_list_is_only_the_callers_rooms_and_paginates(server):
    with connect_peer(server) as alice, connect_peer(server) as bob, connect_peer(server) as carol:
        alice.register("Alice"), bob.register("Bob"), carol.register("Carol")
        ab = alice.ok(R.PRIVATE_ROOM_OPEN, {"peer_id": bob.user["id"]})["room"]
        bc = bob.ok(R.PRIVATE_ROOM_OPEN, {"peer_id": carol.user["id"]})["room"]
        ac = carol.ok(R.PRIVATE_ROOM_OPEN, {"peer_id": alice.user["id"]})["room"]
        alice.ok(R.GROUP_CREATE, {"name": "Not private"})
        page = alice.ok(R.PRIVATE_ROOM_LIST, {"limit": 1})
        assert [r["id"] for r in page["rooms"]] == [ab["id"]] and page["next_after_id"] == ab["id"]
        rest = alice.ok(R.PRIVATE_ROOM_LIST, {"after_id": page["next_after_id"], "limit": 1})
        assert [r["id"] for r in rest["rooms"]] == [ac["id"]] and rest["next_after_id"] is None
        assert bc["id"] not in [r["id"] for r in alice.ok(R.PRIVATE_ROOM_LIST)["rooms"]]
        for bad in ({"after_id": -1}, {"limit": 0}, {"limit": 101}, {"user_id": bob.user["id"]}):
            assert alice.error(R.PRIVATE_ROOM_LIST, bad) == E.INVALID_INPUT


def test_pagination_has_no_gaps_or_duplicates_while_new_messages_arrive(server):
    with connect_peer(server) as alice, connect_peer(server) as bob:
        alice.register("Alice"), bob.register("Bob")
        room = alice.ok(R.GROUP_CREATE, {"name": "paging"})["room"]["id"]
        bob.ok(R.GROUP_JOIN, {"room_id": room})
        before = [alice.say(room, f"old {n}")["message_id"] for n in range(123)]
        seen, cursor, arrived = [], None, []
        latest = alice.ok(R.HISTORY_GET, {"room_id": room, "limit": 50})
        seen += ids(latest["messages"])
        cursor = latest["next_before_id"]
        while cursor is not None:
            # Another member keeps chatting between page requests.
            arrived.append(bob.say(room, f"new while paging {len(arrived)}")["message_id"])
            page = alice.ok(R.HISTORY_GET, {"room_id": room, "before_id": cursor, "limit": 50})
            assert ids(page["messages"]) == sorted(ids(page["messages"]))
            assert all(mid < cursor for mid in ids(page["messages"]))
            seen += ids(page["messages"])
            cursor = page["next_before_id"]
        assert sorted(seen) == before and len(seen) == len(set(seen))
        assert all(mid > before[-1] for mid in arrived)
        # Live events cover the arrivals: the next latest page starts with them.
        assert ids(alice.ok(R.HISTORY_GET, {"room_id": room, "limit": len(arrived)})["messages"]) == arrived
        assert alice.ok(R.HISTORY_GET, {"room_id": room, "before_id": before[0]}) == {
            "messages": [], "next_before_id": None}


def test_outsiders_and_new_members_cannot_read_or_search_before_their_boundary(server):
    with connect_peer(server) as alice, connect_peer(server) as bob, connect_peer(server) as carol:
        alice.register("Alice"), bob.register("Bob"), carol.register("Carol")
        group = alice.ok(R.GROUP_CREATE, {"name": "boundary"})["room"]["id"]
        private = alice.ok(R.PRIVATE_ROOM_OPEN, {"peer_id": bob.user["id"]})["room"]["id"]
        secret = alice.say(group, "secret plan before Bob")
        alice.say(private, "secret private")
        bob.ok(R.GROUP_JOIN, {"room_id": group})
        after = alice.say(group, "secret plan after Bob")
        assert bob.ok(R.HISTORY_GET, {"room_id": group})["messages"] == [after]
        assert ids(bob.ok(R.HISTORY_SEARCH, {"room_id": group, "query": "secret"})["messages"]) == [after["message_id"]]
        assert bob.ok(R.HISTORY_GET, {"room_id": group, "before_id": after["message_id"]})["messages"] == []
        assert ids(alice.ok(R.HISTORY_SEARCH, {"room_id": group, "query": "secret"})["messages"]) == [
            after["message_id"], secret["message_id"]]
        for room in (group, private, 999_999):
            assert carol.error(R.HISTORY_GET, {"room_id": room}) == E.FORBIDDEN
            assert carol.error(R.HISTORY_SEARCH, {"room_id": room, "query": "secret"}) == E.FORBIDDEN
        # Actor fields from the client are rejected rather than trusted.
        assert carol.error(R.HISTORY_GET, {"room_id": group, "user_id": alice.user["id"]}) == E.INVALID_INPUT
        assert carol.drain("MESSAGE_NEW") == []


def test_keyword_search_is_literal_case_insensitive_and_thai_aware(server):
    with connect_peer(server) as alice:
        alice.register("Alice")
        room = alice.ok(R.GROUP_CREATE, {"name": "search"})["room"]["id"]
        texts = ["Deadline Friday", "deadline moved", "100% done", "100 percent", "a_b literal", "axb",
                 "ส่งรายงานวันศุกร์", "ประชุมพรุ่งนี้", "back\\slash"]
        sent = {text: alice.say(room, text)["message_id"] for text in texts}

        def search(query):
            return {sent_text for sent_text, mid in sent.items()
                    if mid in ids(alice.ok(R.HISTORY_SEARCH, {"room_id": room, "query": query})["messages"])}

        assert search("DEADLINE") == {"Deadline Friday", "deadline moved"}
        assert search("100%") == {"100% done"}
        assert search("a_b") == {"a_b literal"}
        assert search("รายงาน") == {"ส่งรายงานวันศุกร์"}
        assert search("  ประชุม  ") == {"ประชุมพรุ่งนี้"}
        assert search("\\") == {"back\\slash"}
        assert search("ไม่มีคำนี้") == set()
        results = alice.ok(R.HISTORY_SEARCH, {"room_id": room, "query": "e", "limit": 2})
        assert ids(results["messages"]) == sorted(ids(results["messages"]), reverse=True)
        more = alice.ok(R.HISTORY_SEARCH, {"room_id": room, "query": "e", "before_id": results["next_before_id"]})
        assert not set(ids(more["messages"])) & set(ids(results["messages"]))


def test_date_range_uses_utc_with_inclusive_start_and_exclusive_end(server):
    with connect_peer(server) as alice:
        alice.register("Alice")
        room = alice.ok(R.GROUP_CREATE, {"name": "dates"})["room"]["id"]
        times = {"late Nov 5 UTC": "2026-11-05T16:59:59.999Z", "Bangkok midnight": "2026-11-05T17:00:00.000Z",
                 "Bangkok evening": "2026-11-06T13:00:00.000Z", "next Bangkok day": "2026-11-06T17:00:00.000Z"}
        sent = {}
        for text, created in times.items():
            sent[text] = alice.say(room, text)["message_id"]
            set_time(server, sent[text], created)

        def between(**window):
            found = ids(alice.ok(R.HISTORY_SEARCH, {"room_id": room, **window})["messages"])
            return {text for text, mid in sent.items() if mid in found}

        # The browser converts the local day 6 Nov 2026 (Asia/Bangkok) to this UTC window.
        bangkok_day = {"from": "2026-11-05T17:00:00.000Z", "to": "2026-11-06T17:00:00.000Z"}
        assert between(**bangkok_day) == {"Bangkok midnight", "Bangkok evening"}
        assert between(**{"from": "2026-11-06T00:00:00+07:00", "to": "2026-11-07T00:00:00+07:00"}) == {
            "Bangkok midnight", "Bangkok evening"}
        assert between(**{"from": "2026-11-06T17:00:00Z"}) == {"next Bangkok day"}
        assert between(**{"to": "2026-11-05T17:00:00Z"}) == {"late Nov 5 UTC"}
        assert between(query="Bangkok", **bangkok_day) == {"Bangkok midnight", "Bangkok evening"}
        assert between(query="evening", **{"from": "2026-11-06T13:00:00.0001Z"}) == set()


@pytest.mark.parametrize("data", [
    {}, {"query": ""}, {"query": "   "}, {"query": "x" * 201}, {"query": "a\x00b"}, {"query": 5},
    {"from": "2026-11-06"}, {"from": "2026-11-06T00:00:00"}, {"from": "yesterday"},
    {"from": "2026-11-06T00:00:00Z", "to": "2026-11-06T00:00:00Z"},
    {"from": "2026-11-07T00:00:00Z", "to": "2026-11-06T00:00:00Z"},
    {"from": "0001-01-01T00:00:00+01:00"}, {"to": "9999-12-31T23:59:59-01:00"},
    {"kind": "image"}, {"query": "x", "limit": 0}, {"query": "x", "limit": 101}, {"query": "x", "limit": True},
    {"query": "x", "before_id": 0}, {"query": "x", "before_id": "5"}, {"query": "x", "sender_id": 1},
])
def test_search_rejects_invalid_input(server, data):
    with connect_peer(server) as alice:
        alice.register("Alice")
        room = alice.ok(R.GROUP_CREATE, {"name": "bad"})["room"]["id"]
        assert alice.error(R.HISTORY_SEARCH, {"room_id": room, **data}) == E.INVALID_INPUT


@pytest.mark.parametrize("data", [{}, {"room_id": "1"}, {"room_id": 1, "limit": 0},
                                  {"room_id": 1, "before_id": -3}, {"room_id": 1, "extra": 1}])
def test_history_get_rejects_invalid_input(server, data):
    with connect_peer(server) as alice:
        alice.register("Alice")
        alice.ok(R.GROUP_CREATE, {"name": "bad"})
        assert alice.error(R.HISTORY_GET, data) == E.INVALID_INPUT


def test_oversized_page_reports_frame_limit_and_smaller_page_succeeds(server):
    with connect_peer(server) as alice:
        alice.register("Alice")
        room = alice.ok(R.GROUP_CREATE, {"name": "large"})["room"]["id"]
        for _ in range(100):
            alice.say(room, "\x01" * 3999 + "x")  # Each control char becomes a 6-byte JSON escape.
        assert alice.error(R.HISTORY_GET, {"room_id": room, "limit": 100}) == E.FRAME_TOO_LARGE
        assert len(alice.ok(R.HISTORY_GET, {"room_id": room, "limit": 25})["messages"]) == 25
        assert alice.ok(R.USERS_LIST)["users"]  # The connection keeps working.


def test_utc_bound_normalises_offsets_and_rounds_up_submilliseconds():
    assert utc_bound("2026-11-06T00:00:00+07:00", "from") == "2026-11-05T17:00:00.000Z"
    assert utc_bound("2026-11-06T13:00:00.0001Z", "from") == "2026-11-06T13:00:00.001Z"
    assert utc_bound("2026-12-31T23:59:59.9999Z", "to") == "2027-01-01T00:00:00.000Z"
    with pytest.raises(ChatError):
        utc_bound("2026-11-06T00:00:00", "from")


def test_search_results_include_file_names_and_kind_filter_uses_same_scope(server, tmp_path):
    with connect_peer(server) as alice:
        alice.register("Alice")
        room = alice.ok(R.GROUP_CREATE, {"name": "files"})["room"]["id"]
        text = alice.say(room, "report draft")
        uploaded = alice.upload(room, "Report-final.pdf", b"%PDF-1.7 fake")
        assert uploaded["ok"], uploaded
        file_message = uploaded["result"]["message"]
        assert ids(alice.ok(R.HISTORY_SEARCH, {"room_id": room, "query": "REPORT"})["messages"]) == [
            file_message["message_id"], text["message_id"]]
        files = alice.ok(R.HISTORY_SEARCH, {"room_id": room, "kind": "file"})["messages"]
        assert files == [file_message] and file_message["text"] is None
        assert set(file_message["attachment"]) == {"id", "name", "size", "sha256"}
        assert Path(server.config.uploads_dir, file_message["attachment"]["name"]).exists() is False
