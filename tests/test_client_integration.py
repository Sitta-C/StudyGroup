"""CP06 desktop controller and worker through real TCP/TLS, without Tk mocks."""

import threading
import time

import pytest

import client.network as network
from client.config import ClientConfig
from client.controller import ClientController
from client.network import NetworkWorker
from shared.message_types import RequestType as R
from shared.message_types import EventType
from shared.protocol import PacketConnection, encode_packet, make_event

PASSWORD = "client test password🔑"


def until(predicate, *clients, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for client in clients:
            client.pump()
        if predicate():
            return
        time.sleep(0.005)
    pytest.fail("Client state did not reach the expected condition before deadline")


def barrier(*clients):
    finished = []
    for client in clients:
        client.request(R.USERS_LIST, {}, lambda result: finished.append(True))
    until(lambda: len(finished) == len(clients), *clients)


@pytest.fixture
def desktop_clients(server, certificates):
    clients = []
    config = ClientConfig("127.0.0.1", server.address[1], certificates / "ca.crt")
    callbacks = []
    for username in ("Alice", "Bob", "Carol"):
        client = ClientController(lambda: callbacks.append(threading.get_ident()))
        clients.append(client)
        client.authenticate(R.REGISTER, config, username, PASSWORD, PASSWORD)
        until(lambda: not client.auth_busy, *clients)
        assert client.info.startswith("สมัครสมาชิก"), (client.phase, client.error)
        client.authenticate(R.LOGIN, config, username, PASSWORD)
        until(lambda: client.authenticated and not client.groups_loading, *clients)
    until(lambda: all(len(c.state.users) == 3 for c in clients), *clients)
    yield clients, config, callbacks
    for client in clients:
        client.close()
        client.worker.thread.join(6)
        assert not client.worker.thread.is_alive()


def test_private_discovery_sender_echo_dedup_drafts_and_ui_thread(desktop_clients):
    (alice, bob, carol), _, callbacks = desktop_clients
    assert all(c.state.user in c.state.users for c in (alice, bob, carol))
    alice.open_private(bob.state.user["id"])
    until(lambda: alice.state.active_room is not None, alice, bob, carol)
    room_id = alice.state.active_room
    text = "  ประชุม ๒ ทุ่ม\nสวัสดี 👋 Café  "
    alice.send(room_id, text)
    until(lambda: room_id in bob.state.rooms and len(bob.state.messages.get(room_id, {})) == 1,
          alice, bob, carol)
    barrier(alice, bob, carol)
    assert len(alice.state.messages[room_id]) == 1
    assert next(iter(bob.state.messages[room_id].values()))["text"] == text
    assert alice.state.drafts[room_id] == ""
    assert bob.state.unread[room_id] == 1
    assert not carol.state.messages
    assert not carol.state.rooms
    bob.select_room(room_id)
    assert room_id not in bob.state.unread
    assert set(callbacks) == {threading.get_ident()}


def test_groups_all_rosters_self_join_and_no_before_join_content(desktop_clients):
    (alice, bob, carol), _, _ = desktop_clients
    alice.create_group("ทีมหนึ่ง")
    until(lambda: alice.state.active_room is not None and len(carol.state.rooms) == 1,
          alice, bob, carol)
    first = alice.state.active_room
    assert [m["id"] for m in bob.state.rooms[first]["members"]] == [alice.state.user["id"]]
    alice.send(first, "ก่อนเข้ากลุ่ม")
    barrier(alice, bob, carol)
    assert first not in bob.state.messages
    bob.select_room(first)
    bob.send(first, "คนนอกส่งไม่ได้")
    assert bob.error
    assert not bob.pending_sends
    bob.join_group(first)
    until(lambda: bob.state.is_member(first) and len(carol.state.rooms[first]["members"]) == 2,
          alice, bob, carol)
    bob.send(first, "หลังเข้ากลุ่ม\nได้แล้ว")
    until(lambda: len(alice.state.messages[first]) == 2 and len(bob.state.messages.get(first, {})) == 1,
          alice, bob, carol)
    barrier(alice, bob, carol)
    assert first not in carol.state.messages
    alice.create_group("ทีมสอง")
    until(lambda: len(carol.state.rooms) == 2, alice, bob, carol)
    assert not carol.state.is_member(first)


def test_group_pagination_is_complete(desktop_clients):
    (alice, bob, carol), _, _ = desktop_clients
    for index in range(53):
        alice.create_group(f"กลุ่ม {index + 1}")
    until(lambda: all(len(c.state.rooms) == 53 and not c.groups_loading for c in (alice, bob, carol)),
          alice, bob, carol)
    assert len({room["name"] for room in carol.state.rooms.values()}) == 53


def test_delayed_room_response_does_not_steal_later_selection(server, desktop_clients, monkeypatch):
    (alice, bob, carol), _, _ = desktop_clients
    alice.create_group("ห้องที่ต้องการอ่าน")
    until(lambda: alice.state.active_room is not None, alice, bob, carol)
    group_id = alice.state.active_room
    entered, release = threading.Event(), threading.Event()
    dispatch = server.router.dispatch

    def delay_private(connection, db, request):
        dispatch(connection, db, request)
        if request["type"] == R.PRIVATE_ROOM_OPEN:
            entered.set()
            assert release.wait(3)

    monkeypatch.setattr(server.router, "dispatch", delay_private)
    try:
        alice.open_private(bob.state.user["id"])
        until(entered.is_set, alice, bob, carol)
        alice.select_room(group_id)
    finally:
        release.set()
    barrier(alice, bob, carol)
    assert len(alice.state.rooms) == 2
    assert alice.state.active_room == group_id


def test_commit_without_ack_keeps_draft_and_never_retries(server, desktop_clients, monkeypatch):
    (alice, bob, carol), config, _ = desktop_clients
    alice.open_private(bob.state.user["id"])
    until(lambda: alice.state.active_room is not None, alice, bob, carol)
    room_id = alice.state.active_room
    dispatch = server.router.dispatch

    def cut_after_commit(connection, db, request):
        dispatch(connection, db, request)
        if request["type"] == R.MESSAGE_SEND:
            connection.request_close()

    monkeypatch.setattr(server.router, "dispatch", cut_after_commit)
    text = "ข้อความที่ยังยืนยันไม่ได้"
    alice.send(room_id, text)
    until(lambda: alice.phase == "disconnected" and room_id in bob.state.messages, alice, bob, carol)
    assert alice.state.drafts[room_id] == text
    assert "ยังยืนยัน" in alice.state.notices[room_id]
    assert not alice.pending_sends
    monkeypatch.setattr(server.router, "dispatch", dispatch)
    alice.authenticate(R.LOGIN, config, "Alice", PASSWORD)
    until(lambda: alice.authenticated and not alice.groups_loading, alice, bob, carol)
    barrier(alice, bob, carol)
    assert alice.state.drafts[room_id] == text
    assert len(bob.state.messages[room_id]) == 1
    with server.database.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM messages WHERE room_id = ?", (room_id,)).fetchone()[0] == 1


def test_new_draft_is_not_erased_by_ack_for_older_text(desktop_clients):
    (alice, bob, carol), _, _ = desktop_clients
    alice.open_private(bob.state.user["id"])
    until(lambda: alice.state.active_room is not None, alice, bob, carol)
    room_id = alice.state.active_room
    alice.send(room_id, "ข้อความแรก")
    alice.state.drafts[room_id] = "ร่างข้อความถัดไป"
    until(lambda: not alice.pending_sends, alice, bob, carol)
    assert alice.state.drafts[room_id] == "ร่างข้อความถัดไป"
    assert len(alice.state.messages[room_id]) == 1


def test_relogin_other_account_clears_old_messages_and_drafts(desktop_clients):
    (alice, bob, carol), config, _ = desktop_clients
    alice.create_group("ห้องของ Alice")
    until(lambda: alice.state.active_room is not None, alice, bob, carol)
    alice.state.drafts[alice.state.active_room] = "ร่างส่วนตัวของ Alice"
    alice.worker.close()
    until(lambda: alice.phase == "disconnected", alice, bob, carol)
    alice.authenticate(R.REGISTER, config, "Dave", PASSWORD, PASSWORD)
    until(lambda: not alice.auth_busy, alice, bob, carol)
    alice.authenticate(R.LOGIN, config, "Dave", PASSWORD)
    until(lambda: alice.authenticated and not alice.groups_loading, alice, bob, carol)
    assert alice.state.user["username"] == "Dave"
    assert alice.state.active_room is None
    assert not alice.state.drafts
    assert not alice.state.messages
    assert not alice.state.notices


def test_logout_cleans_online_users_and_session_memory(desktop_clients):
    (alice, bob, carol), _, _ = desktop_clients
    alice.logout()
    until(lambda: alice.state.user is None and len(bob.state.users) == 2 and len(carol.state.users) == 2,
          alice, bob, carol)
    assert alice.phase == "disconnected"
    assert not alice.state.drafts


@pytest.mark.parametrize("certificate,trust", [("hostname.crt", "ca.crt"), ("server.crt", "other.crt"), ("expired.crt", "ca.crt")])
def test_worker_rejects_invalid_tls_before_credentials(server_factory, certificates, certificate, trust):
    server = server_factory(certificate=certificate)
    worker = NetworkWorker(ClientConfig("127.0.0.1", server.address[1], certificates / trust)).start()
    worker.thread.join(6)
    assert not worker.thread.is_alive()
    events = list(worker.events.queue)
    assert events == [{"type": "disconnected", "reason": "TLS"}]


def test_request_deadline_and_close_do_not_block_main_thread(server, certificates, monkeypatch):
    config = ClientConfig("127.0.0.1", server.address[1], certificates / "ca.crt")
    monkeypatch.setattr(server.router, "dispatch", lambda *args: None)
    worker = NetworkWorker(config, request_timeout=0.15).start()
    worker.submit(R.LOGIN, {"username": "Alice", "password": PASSWORD})
    worker.thread.join(3)
    assert not worker.thread.is_alive()
    assert list(worker.events.queue)[-1] == {"type": "disconnected", "reason": "TIMEOUT"}
    worker = NetworkWorker(config).start()
    before = time.monotonic()
    worker.close()
    assert time.monotonic() - before < 0.1
    worker.thread.join(6)
    assert not worker.thread.is_alive()


def test_worker_is_the_only_tls_io_owner(server, certificates, monkeypatch):
    calls = []
    connect = network.connect

    class TrackedSocket:
        def __init__(self, sock):
            self.sock = sock

        def __getattr__(self, name):
            value = getattr(self.sock, name)
            if name in ("send", "recv", "pending", "close", "shutdown", "setblocking"):
                def call(*args, **kwargs):
                    calls.append(threading.get_ident())
                    return value(*args, **kwargs)
                return call
            return value

    def tracked_connect(*args, **kwargs):
        calls.append(threading.get_ident())
        connection = connect(*args, **kwargs)
        connection.socket = TrackedSocket(connection.socket)
        return connection

    monkeypatch.setattr(network, "connect", tracked_connect)
    worker = NetworkWorker(ClientConfig("127.0.0.1", server.address[1], certificates / "ca.crt")).start()
    try:
        assert worker.events.get(timeout=6)["type"] == "connected"
        worker.submit(R.REGISTER, {"username": "OwnerTest", "password": PASSWORD, "confirm_password": PASSWORD})
        event = worker.events.get(timeout=6)
        assert event["type"] == "packet" and event["packet"]["data"]["ok"]
    finally:
        worker.close()
        worker.thread.join(6)
    assert set(calls) == {worker.thread.ident}
    assert threading.get_ident() not in calls


def test_worker_decodes_fragmented_utf8_and_coalesced_events(server, certificates, monkeypatch):
    def fragmented_send(transport, packet):
        frames = encode_packet(packet)
        frames += encode_packet(make_event(EventType.MESSAGE_NEW, {
            "message_id": 1, "room_id": 1, "sender_id": 1,
            "text": "สวัสดี 👋", "created_at": "2026-11-06T00:00:00Z",
        }))
        frames += encode_packet(make_event(EventType.USERS_UPDATED, {"users": [], "revision": 1}))
        for piece in (frames[:2], frames[2:7], frames[7:19], frames[19:]):
            transport.socket.sendall(piece)

    monkeypatch.setattr(PacketConnection, "send_packet", fragmented_send)
    worker = NetworkWorker(ClientConfig("127.0.0.1", server.address[1], certificates / "ca.crt")).start()
    try:
        assert worker.events.get(timeout=6)["type"] == "connected"
        request_id = worker.submit(R.REGISTER, {"username": "FragmentTest", "password": PASSWORD, "confirm_password": PASSWORD})
        events = [worker.events.get(timeout=6) for _ in range(3)]
        assert events[0]["packet"]["id"] == request_id
        assert events[1]["packet"]["data"]["text"] == "สวัสดี 👋"
        assert events[2]["packet"]["type"] == EventType.USERS_UPDATED
    finally:
        worker.close()
        worker.thread.join(6)


def test_partial_frame_has_a_total_deadline(server, certificates, monkeypatch):
    def truncated_send(transport, packet):
        transport.socket.sendall(encode_packet(packet)[:6])

    monkeypatch.setattr(PacketConnection, "send_packet", truncated_send)
    worker = NetworkWorker(ClientConfig("127.0.0.1", server.address[1], certificates / "ca.crt"),
                           io_timeout=0.3, request_timeout=3).start()
    assert worker.events.get(timeout=6)["type"] == "connected"
    worker.submit(R.REGISTER, {"username": "DeadlineTest", "password": PASSWORD, "confirm_password": PASSWORD})
    worker.thread.join(6)
    assert not worker.thread.is_alive()
    assert list(worker.events.queue)[-1] == {"type": "disconnected", "reason": "TIMEOUT"}


def test_full_ui_queue_closes_without_blocking_worker(server, certificates, monkeypatch):
    original_send = PacketConnection.send_packet

    def burst(transport, packet):
        original_send(transport, packet)
        for revision in range(10):
            original_send(transport, make_event(EventType.USERS_UPDATED, {"users": [], "revision": revision}))

    monkeypatch.setattr(PacketConnection, "send_packet", burst)
    worker = NetworkWorker(ClientConfig("127.0.0.1", server.address[1], certificates / "ca.crt"), queue_size=2).start()
    assert worker.events.get(timeout=6)["type"] == "connected"
    worker.submit(R.REGISTER, {"username": "SlowUITest", "password": PASSWORD, "confirm_password": PASSWORD})
    worker.thread.join(6)
    assert not worker.thread.is_alive()
    assert list(worker.events.queue)[-1]["type"] == "disconnected"


@pytest.mark.parametrize("text", ["", " \n", "a\x00b", "ก" * 4001, "🙂" * 4001])
def test_bad_text_does_not_clear_draft_or_send(desktop_clients, text):
    (alice, bob, carol), _, _ = desktop_clients
    alice.create_group("ทดสอบความยาว")
    until(lambda: alice.state.active_room is not None, alice, bob, carol)
    room_id = alice.state.active_room
    alice.state.drafts[room_id] = text
    alice.send(room_id, text)
    assert alice.error
    assert not alice.pending_sends
    assert alice.state.drafts[room_id] == text
    assert not alice.state.messages
