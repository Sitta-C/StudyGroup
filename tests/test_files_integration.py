"""CP08 chunked file transfer over real WebSocket connections and temporary storage."""

import base64
import hashlib
import os
import re
import sqlite3
import time

import pytest

from server.web import WebServer
from server.web_config import WebConfig
from shared.message_types import ErrorCode as E, RequestType as R
from web_peer import CHUNK, ORIGIN, connect_peer

MiB = 1024 * 1024


@pytest.fixture
def servers(tmp_path):
    started = []
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html><title>StudyGroup</title>")

    def start():
        server = WebServer(WebConfig("127.0.0.1", 0, tmp_path / "data", static, (ORIGIN,))).start()
        started.append(server)
        return server

    def stop(server):
        server.stop()
        started.remove(server)

    start.stop = stop
    yield start
    for server in reversed(started):
        server.stop()
        assert server.files.active_transfers() == 0


@pytest.fixture
def server(servers):
    return servers()


def count(server, table):
    db = sqlite3.connect(server.config.database_path)
    try:
        return db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    finally:
        db.close()


def stored_files(server):
    return sorted(p.name for p in server.config.uploads_dir.iterdir() if p.is_file())


def partials(server):
    return sorted(p.name for p in (server.config.uploads_dir / ".partial").iterdir())


def wait_until(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


def setup_trio(server, alice, bob, carol):
    alice.register("Alice"), bob.register("Bob"), carol.register("Carol")
    room = alice.ok(R.GROUP_CREATE, {"name": "ไฟล์งาน"})["room"]["id"]
    bob.ok(R.GROUP_JOIN, {"room_id": room})
    for peer in (alice, bob, carol):
        peer.drain("GROUPS_UPDATED")
    return room


def begin(peer, room, content=b"abc", **overrides):
    data = {"room_id": room, "name": "notes.txt", "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(), **overrides}
    return peer.request(R.FILE_BEGIN, data)


def chunk(peer, transfer, index, piece):
    return peer.request(R.FILE_CHUNK, {"transfer_id": transfer, "index": index,
                                       "data": base64.b64encode(piece).decode()})


def test_five_mib_roundtrip_hash_matches_and_only_members_receive_it(servers):
    server = servers()
    content = os.urandom(5 * MiB)  # Exactly the limit, 160 chunks of 32 KiB.
    with connect_peer(server) as alice, connect_peer(server) as bob, connect_peer(server) as carol:
        room = setup_trio(server, alice, bob, carol)
        result = alice.upload(room, "ข้อมูลโปรเจกต์ v2.zip", content)
        assert result["ok"], result
        message = result["result"]["message"]
        attachment = message["attachment"]
        assert message["text"] is None and attachment["name"] == "ข้อมูลโปรเจกต์ v2.zip"
        assert attachment["size"] == 5 * MiB and attachment["sha256"] == hashlib.sha256(content).hexdigest()
        assert bob.drain("MESSAGE_NEW") == [message]
        assert carol.drain("MESSAGE_NEW") == []
        downloaded, meta = bob.download(attachment["id"])
        assert downloaded == content and hashlib.sha256(downloaded).hexdigest() == meta["sha256"]
        assert carol.error(R.FILE_GET, {"attachment_id": attachment["id"]}) == E.FORBIDDEN
        assert bob.ok(R.HISTORY_GET, {"room_id": room})["messages"] == [message]
        # The server chose the stored name; nothing derived from the client name is on disk.
        names = stored_files(server)
        assert len(names) == 1 and re.fullmatch(r"[0-9a-f]{32}", names[0]) and partials(server) == []
    servers.stop(server)
    restarted = servers()
    with connect_peer(restarted) as bob:
        bob.login("Bob")
        assert bob.download(attachment["id"])[0] == content


def test_empty_and_small_files_and_last_chunk_length(server):
    with connect_peer(server) as alice:
        alice.register("Alice")
        room = alice.ok(R.GROUP_CREATE, {"name": "small"})["room"]["id"]
        empty = alice.upload(room, "empty.txt", b"")
        assert empty["ok"] and alice.download(empty["result"]["message"]["attachment"]["id"])[0] == b""
        odd = os.urandom(CHUNK + 7)
        uploaded = alice.upload(room, "odd.bin", odd)
        assert alice.download(uploaded["result"]["message"]["attachment"]["id"])[0] == odd


def test_oversize_declarations_and_overflowing_chunks_are_rejected(server):
    with connect_peer(server) as alice:
        alice.register("Alice")
        room = alice.ok(R.GROUP_CREATE, {"name": "limits"})["room"]["id"]
        assert begin(alice, room, size=5 * MiB + 1)["error"]["code"] == E.INVALID_INPUT
        for size in (-1, 1.5, "10", True):
            assert begin(alice, room, size=size)["error"]["code"] == E.INVALID_INPUT
        # Declared 3 bytes, but the real decoded chunk is larger: real bytes count.
        transfer = begin(alice, room)["result"]["transfer_id"]
        assert chunk(alice, transfer, 0, b"abcdef")["error"]["code"] == E.INVALID_INPUT
        assert alice.error(R.FILE_END, {"transfer_id": transfer}) == E.INVALID_INPUT  # Already discarded.
        # Non-final chunks must be exactly 32 KiB, so a split cannot exceed the total.
        content = os.urandom(CHUNK * 2)
        transfer = begin(alice, room, content)["result"]["transfer_id"]
        assert chunk(alice, transfer, 0, content[:100])["error"]["code"] == E.INVALID_INPUT
        assert count(server, "attachments") == 0 and partials(server) == []


def test_out_of_order_duplicate_and_malformed_chunks_abort_the_transfer(server):
    content = os.urandom(CHUNK * 3)
    with connect_peer(server) as alice:
        alice.register("Alice")
        room = alice.ok(R.GROUP_CREATE, {"name": "order"})["room"]["id"]
        for bad_index, prefix in ((1, 0), (0, 1), (-1, 0), ("0", 0)):
            transfer = begin(alice, room, content)["result"]["transfer_id"]
            for index in range(prefix):
                assert chunk(alice, transfer, index, content[index * CHUNK:(index + 1) * CHUNK])["ok"]
            piece = content[bad_index * CHUNK:(bad_index + 1) * CHUNK] if isinstance(bad_index, int) and bad_index >= 0 else content[:CHUNK]
            assert alice.request(R.FILE_CHUNK, {"transfer_id": transfer, "index": bad_index,
                                                "data": base64.b64encode(piece).decode()})["error"]["code"] == E.INVALID_INPUT
            assert chunk(alice, transfer, prefix, content[prefix * CHUNK:(prefix + 1) * CHUNK])["error"]["code"] == E.INVALID_INPUT
        for payload in ("not base64!" + "A" * 43681, "A" * 10, base64.b64encode(b"x" * CHUNK).decode()[:-4] + "a b=", 7):
            transfer = begin(alice, room, content)["result"]["transfer_id"]
            assert alice.request(R.FILE_CHUNK, {"transfer_id": transfer, "index": 0, "data": payload})["error"]["code"] == E.INVALID_INPUT
        assert count(server, "messages") == 0 and partials(server) == []
        assert server.files.active_transfers() == 0


def test_hash_mismatch_and_incomplete_upload_publish_nothing(server):
    content = os.urandom(CHUNK + 1)
    with connect_peer(server) as alice, connect_peer(server) as bob:
        alice.register("Alice"), bob.register("Bob")
        room = alice.ok(R.GROUP_CREATE, {"name": "hash"})["room"]["id"]
        bob.ok(R.GROUP_JOIN, {"room_id": room})
        bob.drain("GROUPS_UPDATED")
        wrong = alice.upload(room, "wrong.bin", content, digest=hashlib.sha256(b"other").hexdigest())
        assert wrong["error"]["code"] == E.INVALID_INPUT and "hash" in wrong["error"]["message"].lower()
        transfer = begin(alice, room, content)["result"]["transfer_id"]
        assert chunk(alice, transfer, 0, content[:CHUNK])["ok"]
        incomplete = alice.request(R.FILE_END, {"transfer_id": transfer})
        assert incomplete["error"]["code"] == E.INVALID_INPUT
        assert alice.error(R.FILE_END, {"transfer_id": transfer}) == E.INVALID_INPUT
        assert count(server, "messages") == count(server, "attachments") == 0
        assert stored_files(server) == [] and partials(server) == [] and bob.drain("MESSAGE_NEW") == []
        assert alice.say(room, "แชตยังใช้ได้")["text"] == "แชตยังใช้ได้"


@pytest.mark.parametrize("name", ["../../etc/passwd", "a/b.txt", "..\\win.ini", "C:evil", "..", ".", "",
                                  " spaced.txt", "line\nbreak", "nul\x00.txt", "rtl‮txt.exe", "x" * 256, 42])
def test_path_traversal_and_unsafe_names_are_rejected(server, name):
    with connect_peer(server) as alice:
        alice.register("Alice")
        room = alice.ok(R.GROUP_CREATE, {"name": "names"})["room"]["id"]
        assert begin(alice, room, name=name)["error"]["code"] == E.INVALID_INPUT
        assert partials(server) == [] and stored_files(server) == []


def test_disconnect_mid_transfer_cleans_up_without_breaking_chat(server):
    content = os.urandom(CHUNK * 4)
    with connect_peer(server) as bob:
        with connect_peer(server) as alice:
            alice.register("Alice")
            bob.register("Bob")
            room = alice.ok(R.GROUP_CREATE, {"name": "drop"})["room"]["id"]
            bob.ok(R.GROUP_JOIN, {"room_id": room})
            transfer = begin(alice, room, content)["result"]["transfer_id"]
            assert chunk(alice, transfer, 0, content[:CHUNK])["ok"]
            assert len(partials(server)) == 1
        assert wait_until(lambda: server.files.active_transfers() == 0 and partials(server) == [])
        assert count(server, "messages") == 0
        assert bob.say(room, "ยังคุยต่อได้")["room_id"] == room
        with connect_peer(server) as alice:
            alice.login("Alice")
            # A new connection cannot resume someone else's (or its old) transfer.
            assert chunk(alice, transfer, 1, content[CHUNK:2 * CHUNK])["error"]["code"] == E.INVALID_INPUT


def test_transfers_belong_to_one_connection_and_room_membership(server):
    content = b"private bytes"
    with connect_peer(server) as alice, connect_peer(server) as bob, connect_peer(server) as carol:
        room = setup_trio(server, alice, bob, carol)
        assert begin(carol, room)["error"]["code"] == E.FORBIDDEN
        assert begin(carol, 999_999)["error"]["code"] == E.FORBIDDEN
        transfer = begin(alice, room, content)["result"]["transfer_id"]
        assert chunk(bob, transfer, 0, content)["error"]["code"] == E.INVALID_INPUT
        assert bob.error(R.FILE_END, {"transfer_id": transfer}) == E.INVALID_INPUT
        assert chunk(alice, transfer, 0, content)["ok"]
        assert alice.ok(R.FILE_END, {"transfer_id": transfer})["message"]["attachment"]["size"] == len(content)
        for bad in ({}, {"transfer_id": transfer, "extra": 1}, {"transfer_id": 5}):
            assert alice.error(R.FILE_END, bad) == E.INVALID_INPUT
        assert begin(alice, room, sha256="A" * 64)["error"]["code"] == E.INVALID_INPUT
        assert alice.error(R.FILE_BEGIN, {"room_id": room, "name": "x", "size": 1, "sha256": "0" * 64,
                                          "sender_id": bob.user["id"]}) == E.INVALID_INPUT


def test_guessed_attachment_ids_and_pre_join_files_are_forbidden(server):
    with connect_peer(server) as alice, connect_peer(server) as bob, connect_peer(server) as carol:
        alice.register("Alice"), bob.register("Bob"), carol.register("Carol")
        group = alice.ok(R.GROUP_CREATE, {"name": "before join"})["room"]["id"]
        private = alice.ok(R.PRIVATE_ROOM_OPEN, {"peer_id": bob.user["id"]})["room"]["id"]
        early = alice.upload(group, "early.txt", b"before Carol")["result"]["message"]["attachment"]["id"]
        dm = alice.upload(private, "dm.txt", b"only Alice and Bob")["result"]["message"]["attachment"]["id"]
        carol.ok(R.GROUP_JOIN, {"room_id": group})
        late = alice.upload(group, "late.txt", b"after Carol")["result"]["message"]["attachment"]["id"]
        assert carol.download(late)[0] == b"after Carol"
        for attachment in (early, dm, late + 1, 2**53 - 1):
            assert carol.error(R.FILE_GET, {"attachment_id": attachment}) == E.FORBIDDEN
        assert bob.download(dm)[0] == b"only Alice and Bob"
        assert carol.ok(R.HISTORY_SEARCH, {"room_id": group, "kind": "file"})["messages"][0]["attachment"]["id"] == late
        assert len(carol.ok(R.HISTORY_SEARCH, {"room_id": group, "kind": "file"})["messages"]) == 1
        for bad in ({"attachment_id": late, "offset": 99}, {"attachment_id": late, "offset": -1},
                    {"attachment_id": "1"}, {"attachment_id": late, "path": "../x"}):
            assert carol.error(R.FILE_GET, bad) == E.INVALID_INPUT


def test_concurrent_transfer_limit_and_idle_expiry(server):
    with connect_peer(server) as alice:
        alice.register("Alice")
        room = alice.ok(R.GROUP_CREATE, {"name": "limit"})["room"]["id"]
        transfers = [begin(alice, room)["result"]["transfer_id"] for _ in range(3)]
        assert begin(alice, room)["error"]["code"] == E.RATE_LIMITED
        server.files.idle_timeout = 0  # Expire everything on the next sweep.
        fresh = begin(alice, room)
        assert fresh["ok"] and len(partials(server)) == 1
        assert chunk(alice, transfers[0], 0, b"abc")["error"]["code"] == E.INVALID_INPUT


def test_leftover_partials_are_removed_on_start(servers, tmp_path):
    partial = tmp_path / "data" / "uploads" / ".partial"
    partial.mkdir(parents=True)
    (partial / "0123.part").write_bytes(b"crashed upload")
    server = servers()
    assert partials(server) == []


def test_logout_on_an_open_socket_ends_unfinished_uploads(server):
    with connect_peer(server) as peer, connect_peer(server) as other:
        peer.register("Alice")
        other.register("Bob")
        room = peer.ok(R.GROUP_CREATE, {"name": "logout"})["room"]["id"]
        for _ in range(3):
            assert begin(peer, room)["ok"]
        assert len(partials(server)) == 3
        peer.ok(R.LOGOUT)
        assert server.files.active_transfers() == 0 and partials(server) == []
        other.ok(R.LOGOUT)
        peer.login("Bob")  # Another account on the same socket starts with free slots.
        bob_room = peer.ok(R.GROUP_CREATE, {"name": "after"})["room"]["id"]
        assert begin(peer, bob_room)["ok"]


def test_transfers_have_a_maximum_lifetime_even_with_steady_chunks(server):
    content = os.urandom(CHUNK * 3)
    with connect_peer(server) as alice:
        alice.register("Alice")
        room = alice.ok(R.GROUP_CREATE, {"name": "drip"})["room"]["id"]
        transfer = begin(alice, room, content)["result"]["transfer_id"]
        assert chunk(alice, transfer, 0, content[:CHUNK])["ok"]
        server.files.max_lifetime = 0  # Activity is recent, but the transfer is too old.
        assert chunk(alice, transfer, 1, content[CHUNK:2 * CHUNK])["error"]["code"] == E.INVALID_INPUT
        assert partials(server) == []


def test_start_removes_stored_files_that_were_never_committed(servers, tmp_path):
    server = servers()
    with connect_peer(server) as alice:
        alice.register("Alice")
        room = alice.ok(R.GROUP_CREATE, {"name": "orphans"})["room"]["id"]
        kept = alice.upload(room, "kept.txt", b"committed")["result"]["message"]["attachment"]["id"]
    servers.stop(server)
    uploads = tmp_path / "data" / "uploads"
    (uploads / ("f" * 32)).write_bytes(b"renamed but never committed")
    (uploads / "notes-by-admin.txt").write_bytes(b"not a stored name; left alone")
    restarted = servers()
    assert len([name for name in stored_files(restarted) if re.fullmatch(r"[0-9a-f]{32}", name)]) == 1
    assert "notes-by-admin.txt" in stored_files(restarted)
    with connect_peer(restarted) as alice:
        alice.login("Alice")
        assert alice.download(kept)[0] == b"committed"
