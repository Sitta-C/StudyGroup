"""CP05 over real TCP/TLS: committed content, identity and event isolation."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import threading

import pytest

from tls_peer import TLSConfig, connect
from server.database import get_messages
from server.main import TLSServer
from shared.message_types import ErrorCode, EventType, RequestType
from shared.protocol import make_request

PASSWORD = "chat test password🔑"


class ChatPeer:
    def __init__(self, transport):
        self.transport = transport
        self.events = []
        self.packets = []
        self.user = None

    def request(self, kind, data=None):
        request = make_request(kind, data if data is not None else {})
        self.transport.send_packet(request)
        while True:
            reply = self.transport.recv_packet()
            assert reply is not None
            self.packets.append(reply)
            if reply.get("id") == request["id"]:
                return reply["data"]
            assert reply["type"] in EventType
            self.events.append(reply)

    def ok(self, kind, data=None):
        reply = self.request(kind, data)
        assert reply["ok"], reply
        return reply["result"]

    def error(self, kind, data, code):
        reply = self.request(kind, data)
        assert reply["ok"] is False
        assert reply["error"]["code"] == code
        return reply["error"]

    def drain(self, kind):
        # A response on this stream follows all earlier queued publications.
        self.ok(RequestType.USERS_LIST)
        matching = [event["data"] for event in self.events if event["type"] == kind]
        self.events = [event for event in self.events if event["type"] != kind]
        return matching


@pytest.fixture
def clients(server, certificates):
    with ExitStack() as stack:
        peers = []
        for name in ("Alice", "Bob", "Carol"):
            transport = stack.enter_context(connect(
                TLSConfig("127.0.0.1", server.address[1], certificates / "ca.crt"), timeout=5,
            ))
            client = ChatPeer(transport)
            client.ok(RequestType.REGISTER, {
                "username": name, "password": PASSWORD, "confirm_password": PASSWORD,
            })
            client.user = client.ok(RequestType.LOGIN, {"username": name, "password": PASSWORD})["user"]
            peers.append(client)
        for client in peers:
            client.ok(RequestType.USERS_LIST)
            client.events.clear()
            client.packets.clear()
        yield peers


def private(alice, bob):
    return alice.ok(RequestType.PRIVATE_ROOM_OPEN, {"peer_id": bob.user["id"]})["room"]


def group(alice, name="งานกลุ่ม 👋"):
    return alice.ok(RequestType.GROUP_CREATE, {"name": name})["room"]


def send(client, room_id, text):
    return client.ok(RequestType.MESSAGE_SEND, {"room_id": room_id, "text": text})["message"]


def test_private_room_reused_both_directions_and_only_pair_sees_messages(server, clients):
    alice, bob, carol = clients
    room = private(alice, bob)
    assert set(room) == {"id", "kind", "name", "created_by", "created_at", "members"}
    assert [m["id"] for m in room["members"]] == [alice.user["id"], bob.user["id"]]
    assert private(bob, alice) == room
    assert private(alice, carol)["id"] != room["id"]
    text = "  ประชุม ๒ ทุ่ม\nสวัสดี 👋 Café  "
    message = send(alice, room["id"], text)
    assert message["text"] == text
    assert message["sender_id"] == alice.user["id"]
    assert message["created_at"].endswith("Z")
    assert alice.drain(EventType.MESSAGE_NEW) == [message]
    assert bob.drain(EventType.MESSAGE_NEW) == [message]
    assert carol.drain(EventType.MESSAGE_NEW) == []
    assert all(c.drain(EventType.GROUPS_UPDATED) == [] for c in clients)
    with server.database.connect() as db:
        row = db.execute("SELECT * FROM messages WHERE id = ?", (message["message_id"],)).fetchone()
        assert row["text"] == text
        assert row["sender_id"] == alice.user["id"]
    # Acknowledgement precedes the sender's echo on the same stream.
    sent = [p for p in alice.packets if p["type"] == EventType.MESSAGE_NEW][0]
    index = alice.packets.index(sent)
    assert alice.packets[index - 1]["data"]["result"]["message"] == message


def test_groups_public_rosters_self_join_and_private_content_stays_hidden(server, clients):
    alice, bob, carol = clients
    first, second = group(alice, "  กลุ่มหนึ่ง  "), group(alice, "กลุ่มสอง")
    third = group(bob, "กลุ่มอื่น")
    assert first["name"] == "กลุ่มหนึ่ง"
    assert [m["id"] for m in first["members"]] == [alice.user["id"]]
    assert [m["id"] for m in third["members"]] == [bob.user["id"]]
    private(alice, bob)
    before_join = send(alice, first["id"], "ข้อความก่อนเข้ากลุ่ม")
    for client in clients:
        listing = client.ok(RequestType.GROUP_LIST)
        assert listing == {"groups": [first, second, third], "next_after_id": None}
        assert client.drain(EventType.GROUPS_UPDATED) == [{"room_id": r["id"]} for r in (first, second, third)]
    assert bob.drain(EventType.MESSAGE_NEW) == carol.drain(EventType.MESSAGE_NEW) == []
    assert alice.drain(EventType.MESSAGE_NEW) == [before_join]
    joined = bob.ok(RequestType.GROUP_JOIN, {"room_id": first["id"]})["room"]
    assert [m["id"] for m in joined["members"]] == [alice.user["id"], bob.user["id"]]
    assert bob.ok(RequestType.GROUP_JOIN, {"room_id": first["id"]})["room"] == joined
    for client in clients:
        assert client.drain(EventType.GROUPS_UPDATED) == [{"room_id": first["id"]}]
    after_join = send(bob, first["id"], "สมาชิกใหม่ส่งข้อความได้")
    assert alice.drain(EventType.MESSAGE_NEW) == bob.drain(EventType.MESSAGE_NEW) == [after_join]
    assert carol.drain(EventType.MESSAGE_NEW) == []
    assert carol.ok(RequestType.GROUP_LIST)["groups"][0] == joined
    with server.database.connect() as db:
        assert [m["id"] for m in get_messages(db, bob.user["id"], first["id"])] == [after_join["message_id"]]
        member = db.execute("SELECT * FROM room_members WHERE room_id = ? AND user_id = ?",
                            (first["id"], bob.user["id"])).fetchone()
        assert member["visible_after_message_id"] == before_join["message_id"]


def test_room_id_probing_and_sender_spoofing_do_not_write_or_leak(server, clients):
    alice, bob, carol = clients
    rooms = (private(alice, bob)["id"], group(alice)["id"], 999999)
    for room_id in rooms:
        carol.error(RequestType.MESSAGE_SEND, {"room_id": room_id, "text": "guess"}, ErrorCode.FORBIDDEN)
    for data in ({"room_id": rooms[0], "text": "spoof", "sender_id": alice.user["id"]},
                 {"room_id": rooms[1], "text": "spoof", "user_id": alice.user["id"]},
                 {"room_id": rooms[0], "text": "spoof", "username": "Alice"}):
        carol.error(RequestType.MESSAGE_SEND, data, ErrorCode.INVALID_INPUT)
    for room_id in (rooms[0], rooms[-1]):
        carol.error(RequestType.GROUP_JOIN, {"room_id": room_id}, ErrorCode.FORBIDDEN)
    carol.error(RequestType.GROUP_JOIN, {"room_id": rooms[1], "user_id": bob.user["id"]}, ErrorCode.INVALID_INPUT)
    carol.error(RequestType.GROUP_CREATE, {"name": "spoof", "members": [alice.user["id"]]}, ErrorCode.INVALID_INPUT)
    for client in clients:
        assert client.drain(EventType.MESSAGE_NEW) == []
    with server.database.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM room_members WHERE user_id = ?", (carol.user["id"],)).fetchone()[0] == 0


@pytest.mark.parametrize("kind,data", [
    (RequestType.PRIVATE_ROOM_OPEN, {}),
    (RequestType.PRIVATE_ROOM_OPEN, {"peer_id": True}),
    (RequestType.PRIVATE_ROOM_OPEN, {"peer_id": 0}),
    (RequestType.PRIVATE_ROOM_OPEN, {"peer_id": 2**63}),
    (RequestType.PRIVATE_ROOM_OPEN, {"peer_id": "2"}),
    (RequestType.GROUP_JOIN, {"room_id": 1.0}),
    (RequestType.GROUP_JOIN, {"room_id": -1}),
    (RequestType.GROUP_JOIN, {"room_id": None}),
    (RequestType.GROUP_CREATE, {"name": "   "}),
    (RequestType.GROUP_CREATE, {"name": "ก" * 101}),
    (RequestType.GROUP_CREATE, {"name": "a\x00b"}),
    (RequestType.GROUP_CREATE, {"name": []}),
    (RequestType.MESSAGE_SEND, {"room_id": 1, "text": "\n\t"}),
    (RequestType.MESSAGE_SEND, {"room_id": 1, "text": "a" * 4001}),
    (RequestType.MESSAGE_SEND, {"room_id": 1, "text": "a\x00b"}),
    (RequestType.MESSAGE_SEND, {"room_id": 1, "text": None}),
    (RequestType.MESSAGE_SEND, {"room_id": True, "text": "test"}),
    (RequestType.MESSAGE_SEND, {"room_id": 1, "text": "test", "message_id": 2}),
    (RequestType.GROUP_LIST, {"limit": True}),
    (RequestType.GROUP_LIST, {"limit": 0}),
    (RequestType.GROUP_LIST, {"limit": 101}),
    (RequestType.GROUP_LIST, {"after_id": -1}),
    (RequestType.GROUP_LIST, {"after_id": 2**63}),
    (RequestType.GROUP_LIST, {"room_id": 1}),
])
def test_invalid_chat_fields_leave_connection_usable(server, certificates, kind, data):
    with connect(TLSConfig("127.0.0.1", server.address[1], certificates / "ca.crt"), timeout=5) as transport:
        client = ChatPeer(transport)
        client.ok(RequestType.REGISTER, {"username": "Alice", "password": PASSWORD, "confirm_password": PASSWORD})
        client.ok(RequestType.LOGIN, {"username": "Alice", "password": PASSWORD})
        client.error(kind, data, ErrorCode.INVALID_INPUT)
        assert client.ok(RequestType.GROUP_LIST) == {"groups": [], "next_after_id": None}
        with server.database.connect() as db:
            assert db.execute("SELECT COUNT(*) FROM rooms").fetchone()[0] == 0
            assert db.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0


def test_private_open_rejects_self_missing_peer_and_actor_override(clients):
    alice, bob, _ = clients
    alice.error(RequestType.PRIVATE_ROOM_OPEN, {"peer_id": alice.user["id"]}, ErrorCode.INVALID_INPUT)
    alice.error(RequestType.PRIVATE_ROOM_OPEN, {"peer_id": 999999}, ErrorCode.FORBIDDEN)
    alice.error(RequestType.PRIVATE_ROOM_OPEN, {"peer_id": bob.user["id"], "user_id": 3}, ErrorCode.INVALID_INPUT)


def test_group_listing_pagination_and_empty_page(clients):
    alice, bob, carol = clients
    assert carol.ok(RequestType.GROUP_LIST) == {"groups": [], "next_after_id": None}
    groups = [group(alice, f"กลุ่ม {i}") for i in range(3)]
    assert bob.ok(RequestType.GROUP_LIST, {"limit": 2}) == {"groups": groups[:2], "next_after_id": groups[1]["id"]}
    assert bob.ok(RequestType.GROUP_LIST, {"limit": 2, "after_id": groups[1]["id"]}) == {"groups": groups[2:], "next_after_id": None}
    assert bob.ok(RequestType.GROUP_LIST, {"after_id": groups[-1]["id"]}) == {"groups": [], "next_after_id": None}


def test_concurrent_private_opens_use_single_persisted_room(server, clients):
    alice, bob, _ = clients
    barrier = threading.Barrier(2)

    def open_room(pair):
        caller, target = pair
        barrier.wait(timeout=5)
        return private(caller, target)

    with ThreadPoolExecutor(max_workers=2) as pool:
        rooms = list(pool.map(open_room, ((alice, bob), (bob, alice))))
    assert rooms[0] == rooms[1]
    with server.database.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM rooms").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM room_members").fetchone()[0] == 2


def test_concurrent_sends_deliver_same_commit_order_only_to_members(server, clients):
    alice, bob, carol = clients
    room = group(alice)
    bob.ok(RequestType.GROUP_JOIN, {"room_id": room["id"]})
    barrier = threading.Barrier(2)

    def write(client):
        barrier.wait(timeout=5)
        return [send(client, room["id"], f"{client.user['username']} ข้อความ {i}") for i in range(12)]

    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(write, (alice, bob)))
    events = [client.drain(EventType.MESSAGE_NEW) for client in clients]
    assert events[0] == events[1]
    assert len(events[0]) == 24
    assert events[2] == []
    ids = [m["message_id"] for m in events[0]]
    assert ids == sorted(set(ids))
    assert set(ids) == {m["message_id"] for batch in replies for m in batch}
    with server.database.connect() as db:
        assert [m["id"] for m in get_messages(db, bob.user["id"], room["id"])] == ids


@pytest.mark.parametrize("join_first", [False, True])
def test_join_send_boundary_cannot_deliver_prejoin_messages(server, clients, monkeypatch, join_first):
    alice, bob, carol = clients
    room = group(alice)
    gate, release = threading.Event(), threading.Event()
    import server.handlers.chat as chat

    name = "join_group" if join_first else "add_text_message"
    original = getattr(chat, name)

    def paused(*args, **kwargs):
        result = original(*args, **kwargs)
        gate.set()
        assert release.wait(timeout=5)
        return result

    monkeypatch.setattr(chat, name, paused)
    attempted = threading.Event()
    original_handle = server.router.chat.handle

    def handle(connection, db, request):
        waiting_actor = alice if join_first else bob
        if connection.user["id"] == waiting_actor.user["id"]:
            attempted.set()
        return original_handle(connection, db, request)

    monkeypatch.setattr(server.router.chat, "handle", handle)
    with ThreadPoolExecutor(max_workers=2) as pool:
        if join_first:
            first = pool.submit(bob.ok, RequestType.GROUP_JOIN, {"room_id": room["id"]})
            assert gate.wait(timeout=5)
            second = pool.submit(send, alice, room["id"], "ระหว่างเข้ากลุ่ม")
        else:
            first = pool.submit(send, alice, room["id"], "ก่อนเข้ากลุ่ม")
            assert gate.wait(timeout=5)
            second = pool.submit(bob.ok, RequestType.GROUP_JOIN, {"room_id": room["id"]})
        try:
            assert attempted.wait(timeout=5)
        finally:
            release.set()
        results = (first.result(timeout=5), second.result(timeout=5))
    message = results[1] if join_first else results[0]
    assert bob.drain(EventType.MESSAGE_NEW) == ([message] if join_first else [])
    assert carol.drain(EventType.MESSAGE_NEW) == []
    with server.database.connect() as db:
        assert [m["id"] for m in get_messages(db, bob.user["id"], room["id"])] == ([message["message_id"]] if join_first else [])


def test_failed_storage_transaction_sends_no_success_or_event(server, clients, monkeypatch):
    alice, bob, _ = clients
    room = private(alice, bob)
    import server.handlers.chat as chat
    original = chat.add_text_message

    def failing(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("simulated failure after insert")

    monkeypatch.setattr(chat, "add_text_message", failing)
    alice.error(RequestType.MESSAGE_SEND, {"room_id": room["id"], "text": "rollback"}, ErrorCode.INTERNAL_ERROR)
    assert alice.drain(EventType.MESSAGE_NEW) == bob.drain(EventType.MESSAGE_NEW) == []
    with server.database.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0


def test_publications_observe_committed_data_from_another_connection(server, clients, monkeypatch):
    alice, bob, _ = clients
    observed = []
    original = server.registry.publish

    def publish(packet, **kwargs):
        with server.database.connect() as db:
            if packet["type"] == EventType.MESSAGE_NEW:
                assert db.execute("SELECT 1 FROM messages WHERE id = ?", (packet["data"]["message_id"],)).fetchone()
            else:
                assert db.execute("SELECT 1 FROM rooms WHERE id = ?", (packet["data"]["room_id"],)).fetchone()
        observed.append(packet["type"])
        original(packet, **kwargs)

    monkeypatch.setattr(server.registry, "publish", publish)
    room = group(alice)
    bob.ok(RequestType.GROUP_JOIN, {"room_id": room["id"]})
    send(alice, room["id"], "commit ก่อน event")
    alice.ok(RequestType.USERS_LIST)
    assert observed == [EventType.GROUPS_UPDATED, EventType.GROUPS_UPDATED, EventType.MESSAGE_NEW]


def test_logout_and_unauthenticated_connections_receive_no_chat_events(server, clients, certificates):
    alice, bob, carol = clients
    room = private(alice, bob)
    bob.ok(RequestType.LOGOUT)
    bob.error(RequestType.MESSAGE_SEND, {"room_id": room["id"], "text": "after logout"}, ErrorCode.AUTH_REQUIRED)
    with connect(TLSConfig("127.0.0.1", server.address[1], certificates / "ca.crt"), timeout=5) as transport:
        outsider = ChatPeer(transport)
        group(alice)
        send(alice, room["id"], "offline recipient")
        bob.error(RequestType.GROUP_LIST, {}, ErrorCode.AUTH_REQUIRED)
        outsider.error(RequestType.GROUP_LIST, {}, ErrorCode.AUTH_REQUIRED)
        assert not any(e["type"] in (EventType.GROUPS_UPDATED, EventType.MESSAGE_NEW) for e in bob.events)
        assert outsider.events == []
    bob.ok(RequestType.LOGIN, {"username": "Bob", "password": PASSWORD})
    message = send(alice, room["id"], "online again")
    assert bob.drain(EventType.MESSAGE_NEW) == [message]
    assert carol.drain(EventType.MESSAGE_NEW) == []


def test_maximum_unicode_message_round_trips(clients):
    alice, bob, carol = clients
    room = private(alice, bob)
    message = send(alice, room["id"], "🔑" * 4000)
    assert len(message["text"].encode("utf-8")) == 16000
    assert bob.drain(EventType.MESSAGE_NEW) == [message]
    assert carol.drain(EventType.MESSAGE_NEW) == []


def test_oversized_roster_response_is_recoverable_and_join_rolls_back(server, clients, monkeypatch):
    alice, bob, _ = clients
    rooms = [group(alice, f"กลุ่ม {i}") for i in range(2)]
    for client in clients:
        client.drain(EventType.GROUPS_UPDATED)
    import shared.protocol as protocol
    # Reduce the frame cap to exercise real encoding without thousands of
    # accounts. Existing presence events and single-room responses still fit.
    single = protocol.make_response("x" * 32, {"groups": rooms[:1], "next_after_id": rooms[0]["id"]})
    cap = len(protocol.encode_packet(single)) - protocol.HEADER.size
    monkeypatch.setattr(protocol, "MAX_FRAME_BYTES", cap)
    bob.error(RequestType.GROUP_LIST, {}, ErrorCode.FRAME_TOO_LARGE)
    assert bob.ok(RequestType.GROUP_LIST, {"limit": 1})["groups"] == rooms[:1]
    bob.error(RequestType.GROUP_JOIN, {"room_id": rooms[0]["id"]}, ErrorCode.FRAME_TOO_LARGE)
    assert all(client.drain(EventType.GROUPS_UPDATED) == [] for client in clients)
    with server.database.connect() as db:
        assert db.execute("SELECT 1 FROM room_members WHERE room_id = ? AND user_id = ?",
                          (rooms[0]["id"], bob.user["id"])).fetchone() is None


def test_restart_retains_rooms_members_boundaries_and_messages(server, clients, certificates):
    alice, bob, _ = clients
    dm = private(alice, bob)
    room = group(alice)
    old = send(alice, room["id"], "ก่อนเข้ากลุ่ม")
    bob.ok(RequestType.GROUP_JOIN, {"room_id": room["id"]})
    new = send(bob, room["id"], "หลังเข้ากลุ่ม")
    direct = send(alice, dm["id"], "ส่วนตัวถาวร")
    server.stop()
    with TLSServer(server.config) as reopened:
        with connect(TLSConfig("127.0.0.1", reopened.address[1], certificates / "ca.crt"), timeout=5) as transport:
            client = ChatPeer(transport)
            client.error(RequestType.GROUP_LIST, {}, ErrorCode.AUTH_REQUIRED)
            client.ok(RequestType.LOGIN, {"username": "Bob", "password": PASSWORD})
            assert client.ok(RequestType.PRIVATE_ROOM_OPEN, {"peer_id": alice.user["id"]})["room"] == dm
            assert len(client.ok(RequestType.GROUP_LIST)["groups"][0]["members"]) == 2
        with reopened.database.connect() as db:
            assert [m["id"] for m in get_messages(db, bob.user["id"], room["id"])] == [new["message_id"]]
            assert [m["id"] for m in get_messages(db, alice.user["id"], room["id"])] == [old["message_id"], new["message_id"]]
            assert [m["id"] for m in get_messages(db, bob.user["id"], dm["id"])] == [direct["message_id"]]


def test_legacy_tls_framing_serves_history_search_and_file_transfer(server, clients):
    """CP07/CP08 handlers are transport-neutral: the same commands over TCP/TLS frames."""
    import base64
    import hashlib

    alice, bob, carol = clients
    room = group(alice)["id"]
    bob.ok(RequestType.GROUP_JOIN, {"room_id": room})
    sent = send(alice, room, "TLS history ไทย")
    assert bob.ok(RequestType.HISTORY_GET, {"room_id": room}) == {"messages": [sent], "next_before_id": None}
    assert bob.ok(RequestType.HISTORY_SEARCH, {"room_id": room, "query": "tls"})["messages"] == [sent]
    content = bytes(range(256)) * 200  # 51,200 bytes: one full 32 KiB chunk and a remainder.
    begin = alice.ok(RequestType.FILE_BEGIN, {"room_id": room, "name": "tls.bin", "size": len(content),
                                              "sha256": hashlib.sha256(content).hexdigest()})
    for index in range(begin["chunks"]):
        piece = content[index * begin["chunk_size"]:(index + 1) * begin["chunk_size"]]
        alice.ok(RequestType.FILE_CHUNK, {"transfer_id": begin["transfer_id"], "index": index,
                                          "data": base64.b64encode(piece).decode()})
    attachment = alice.ok(RequestType.FILE_END, {"transfer_id": begin["transfer_id"]})["message"]["attachment"]
    received, offset = b"", 0
    while True:
        chunk = bob.ok(RequestType.FILE_GET, {"attachment_id": attachment["id"], "offset": offset})
        received += base64.b64decode(chunk["data"])
        offset = len(received)
        if chunk["done"]:
            break
    assert hashlib.sha256(received).hexdigest() == attachment["sha256"] and received == content
    carol.error(RequestType.FILE_GET, {"attachment_id": attachment["id"]}, ErrorCode.FORBIDDEN)
    assert [event["attachment"]["id"] for event in bob.drain(EventType.MESSAGE_NEW) if "attachment" in event] == [attachment["id"]]
    assert carol.drain(EventType.MESSAGE_NEW) == []
