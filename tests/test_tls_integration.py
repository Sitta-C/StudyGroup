"""Real loopback TCP/TLS, temporary CA/keys and SQLite. No application secrets."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
import json
import os
from pathlib import Path
import select
import signal
import socket
import ssl
import subprocess
import sys
import threading
import time

from argon2 import PasswordHasher, Type
import pytest

from client.config import ClientConfig
from client.network import connect
from server.config import ServerConfig
from server.database import create_user, find_user_for_login
from server.main import ServerLimits, TLSServer
from server.rate_limit import AuthRateLimiter
from shared.message_types import ErrorCode, EventType, RequestType
from shared.protocol import HEADER, MAX_FRAME_BYTES, encode_packet, make_event, make_request, make_response

PASSWORD = "รหัสผ่านทดสอบ🔑"


class Peer:
    def __init__(self, transport):
        self.transport = transport
        self.events = []

    def request(self, kind, data=None):
        packet = make_request(kind, data or {})
        self.transport.send_packet(packet)
        while True:
            reply = self.transport.recv_packet()
            assert reply is not None
            if reply.get("id") == packet["id"]:
                return reply["data"]
            assert reply["type"] == EventType.USERS_UPDATED
            self.events.append(reply["data"])

    def register(self, name, password=PASSWORD):
        return self.request(RequestType.REGISTER, {
            "username": name, "password": password, "confirm_password": password,
        })

    def login(self, name, password=PASSWORD):
        return self.request(RequestType.LOGIN, {"username": name, "password": password})

    def online(self, names):
        while True:
            if self.events:
                event = self.events.pop(0)
            else:
                packet = self.transport.recv_packet()
                assert packet["type"] == EventType.USERS_UPDATED
                event = packet["data"]
            assert all(set(user) == {"id", "username"} for user in event["users"])
            if {user["username"] for user in event["users"]} == set(names):
                return event


@contextmanager
def peer(server, certificates, *, host="127.0.0.1", ca="ca.crt"):
    with connect(ClientConfig(host, server.address[1], certificates / ca), timeout=3) as transport:
        yield Peer(transport)


def success(reply):
    assert reply["ok"], reply
    return reply["result"]


def error(reply, code):
    assert reply["ok"] is False
    assert reply["error"]["code"] == code
    return reply["error"]["message"]


def wait_until(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    assert predicate()


def test_register_login_online_logout_and_relogin(server, certificates):
    with peer(server, certificates) as alice, peer(server, certificates) as bob:
        a = success(alice.register("Alice"))["user"]
        b = success(bob.register("Bob"))["user"]
        assert server.registry.users() == []  # Registration does not log in.
        with server.database.connect() as db:
            row = find_user_for_login(db, "ALICE")
            assert row["password_hash"].startswith("$argon2id$")
            assert PasswordHasher().verify(row["password_hash"], PASSWORD)
            assert PASSWORD not in row["password_hash"]
        assert success(alice.login("aLiCe"))["user"] == a
        first = alice.online({"Alice"})
        assert success(bob.login("BOB"))["user"] == b
        assert alice.online({"Alice", "Bob"})["revision"] > first["revision"]
        bob.online({"Alice", "Bob"})
        assert success(alice.request(RequestType.USERS_LIST)) == {"users": [a, b]}
        success(bob.request(RequestType.LOGOUT))
        alice.online({"Alice"})
        bob.online({"Alice"})  # Logout response is followed by the final snapshot.
        error(bob.request(RequestType.USERS_LIST), ErrorCode.AUTH_REQUIRED)
        error(bob.request(RequestType.LOGOUT), ErrorCode.AUTH_REQUIRED)
        success(bob.login("Bob"))
        bob.online({"Alice", "Bob"})


@pytest.mark.parametrize("kind", [k for k in RequestType if k not in (RequestType.REGISTER, RequestType.LOGIN)])
def test_all_protected_requests_require_connection_authentication(server, certificates, kind):
    with peer(server, certificates) as client:
        error(client.request(kind, {"user_id": 1, "sender_id": 1, "username": "Alice"}), ErrorCode.AUTH_REQUIRED)


def test_wrong_password_unknown_account_share_generic_error_and_connection_remains_usable(server, certificates):
    with peer(server, certificates) as client:
        success(client.register("Alice"))
        first = error(client.login("Alice", "wrong password"), ErrorCode.AUTH_FAILED)
        assert error(client.login("Unknown", "wrong password"), ErrorCode.AUTH_FAILED) == first
        assert error(client.login("invalid name"), ErrorCode.AUTH_FAILED) == first
        assert server.registry.users() == []
        success(client.login("Alice"))


def test_case_insensitive_duplicate_registration_and_no_hash_in_responses(server, certificates):
    with peer(server, certificates) as client:
        created = success(client.register("Alice"))
        assert set(created) == {"user"}
        assert set(created["user"]) == {"id", "username"}
        error(client.register("ALICE"), ErrorCode.USERNAME_TAKEN)
        with server.database.connect() as db:
            assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


@pytest.mark.parametrize("change", [
    {"username": "ab"}, {"username": "ผู้ใช้"}, {"username": 123},
    {"password": "short", "confirm_password": "short"}, {"password": None},
    {"password": "a" * 129}, {"confirm_password": "different"},
    {"user_id": 1}, {"sender_id": 1}, {"password_hash": "$argon2id$forged"},
])
def test_register_validation(server, certificates, change):
    with peer(server, certificates) as client:
        data = {"username": "Alice", "password": PASSWORD, "confirm_password": PASSWORD} | change
        error(client.request(RequestType.REGISTER, data), ErrorCode.INVALID_INPUT)
        assert server.registry.users() == []
        with server.database.connect() as db:
            assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def test_simultaneous_case_insensitive_registration(server, certificates):
    barrier = threading.Barrier(2)

    def register(name):
        with peer(server, certificates) as client:
            barrier.wait(timeout=3)
            return client.register(name)

    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(register, ("Alice", "ALICE")))
    assert sum(r["ok"] for r in replies) == 1
    error(next(r for r in replies if not r["ok"]), ErrorCode.USERNAME_TAKEN)


def test_simultaneous_login_has_one_winner_and_loser_does_not_disconnect_winner(server, certificates):
    with peer(server, certificates) as first, peer(server, certificates) as second:
        success(first.register("Alice"))
        barrier = threading.Barrier(2)

        def login(client):
            barrier.wait(timeout=3)
            return client.login("ALICE")

        with ThreadPoolExecutor(max_workers=2) as pool:
            replies = list(pool.map(login, (first, second)))
        assert sum(reply["ok"] for reply in replies) == 1
        winner, loser = (first, second) if replies[0]["ok"] else (second, first)
        error(next(r for r in replies if not r["ok"]), ErrorCode.ALREADY_LOGGED_IN)
        loser.transport.close()
        assert len(success(winner.request(RequestType.USERS_LIST))["users"]) == 1
        winner.online({"Alice"})
        error(winner.login("Alice"), ErrorCode.ALREADY_LOGGED_IN)


def test_packet_identity_spoofing_cannot_change_actor_or_logout_another_user(server, certificates):
    with peer(server, certificates) as alice, peer(server, certificates) as bob:
        a = success(alice.register("Alice"))["user"]
        b = success(bob.register("Bob"))["user"]
        error(bob.request(RequestType.LOGIN, {"username": "Bob", "password": PASSWORD, "user_id": a["id"]}), ErrorCode.INVALID_INPUT)
        success(alice.login("Alice"))
        success(bob.login("Bob"))
        for kind in (RequestType.LOGOUT, RequestType.USERS_LIST):
            error(bob.request(kind, {"user_id": a["id"]}), ErrorCode.INVALID_INPUT)
        assert success(bob.request(RequestType.USERS_LIST))["users"] == [a, b]
        # Chat commands reject a supplied identity before touching room data.
        error(bob.request(RequestType.MESSAGE_SEND, {"sender_id": a["id"], "room_id": 1, "text": "spoof"}), ErrorCode.INVALID_INPUT)
        assert bob.transport.socket.version() in ("TLSv1.2", "TLSv1.3")


def test_online_cleanup_on_eof_then_relogin_old_cleanup_cannot_remove_new_session(server, certificates):
    with peer(server, certificates) as observer, peer(server, certificates) as old:
        success(observer.register("Observer"))
        success(old.register("Alice"))
        success(observer.login("Observer"))
        success(old.login("Alice"))
        observer.online({"Alice", "Observer"})
        with server.registry._lock:
            previous = next(c for c in server.registry._sessions.values() if c.user["username"] == "Alice")
        old.transport.close()
        observer.online({"Observer"})
        with peer(server, certificates) as fresh:
            success(fresh.login("Alice"))
            fresh.online({"Alice", "Observer"})
            server.registry.logout(previous)  # Delayed second cleanup.
            assert len(success(fresh.request(RequestType.USERS_LIST))["users"]) == 2


@pytest.mark.parametrize("payload", [
    HEADER.pack(0), HEADER.pack(MAX_FRAME_BYTES + 1),
    HEADER.pack(4) + b"nope", HEADER.pack(1) + b"\xff",
    encode_packet(make_event(EventType.USERS_UPDATED, {"users": [{"id": 9}]})),
    encode_packet(make_response("forged", {"user": {"id": 9}})),
])
def test_invalid_frames_and_client_events_close_and_cleanup(server, certificates, payload):
    with peer(server, certificates) as observer, peer(server, certificates) as client:
        success(observer.register("Observer"))
        success(client.register("Alice"))
        success(observer.login("Observer"))
        success(client.login("Alice"))
        observer.online({"Alice", "Observer"})
        client.online({"Alice", "Observer"})
        client.transport.socket.sendall(payload)
        observer.online({"Observer"})
        assert client.transport.recv_packet() is None


def test_truncated_frame_cleanup(server, certificates):
    with peer(server, certificates) as client:
        success(client.register("Alice"))
        success(client.login("Alice"))
        client.online({"Alice"})
        client.transport.socket.sendall(HEADER.pack(200) + b"{")
        client.transport.close()
        wait_until(lambda: server.registry.users() == [])


@pytest.mark.parametrize("which", ["untrusted", "hostname", "expired"])
def test_certificate_rejection_precedes_any_credentials(server_factory, certificates, which):
    server = server_factory(certificate="server.crt" if which == "untrusted" else f"{which}.crt")
    config = ClientConfig("127.0.0.1", server.address[1],
                          certificates / ("other.crt" if which == "untrusted" else "ca.crt"))
    with pytest.raises(ssl.SSLCertVerificationError):
        # connect cannot return a transport capable of sending credentials.
        connect(config, timeout=3)
    with server.database.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    assert server.registry.users() == []
    wait_until(lambda: not server._connections)


def test_dns_hostname_certificate_is_accepted(server, certificates):
    with peer(server, certificates, host="localhost") as client:
        success(client.register("Alice"))


def test_account_login_limit_is_case_insensitive_and_survives_reconnect(server_factory, certificates):
    server = server_factory(limiter=AuthRateLimiter(address_limit=100, account_limit=2))
    with peer(server, certificates) as client:
        success(client.register("Alice"))
        error(client.login("ALICE", "wrong password"), ErrorCode.AUTH_FAILED)
    with peer(server, certificates) as client:
        error(client.login("alice", "wrong password"), ErrorCode.AUTH_FAILED)
    with peer(server, certificates) as client:
        error(client.login("Alice"), ErrorCode.RATE_LIMITED)
        assert server.registry.users() == []


def test_address_limit_survives_new_accounts_and_reconnects(server_factory, certificates):
    server = server_factory(limiter=AuthRateLimiter(address_limit=2, account_limit=100))
    for name in ("Unknown1", "Unknown2"):
        with peer(server, certificates) as client:
            error(client.login(name), ErrorCode.AUTH_FAILED)
    with peer(server, certificates) as client:
        error(client.login("Unknown3"), ErrorCode.RATE_LIMITED)
        error(client.register("NewAccount"), ErrorCode.RATE_LIMITED)


def test_logs_and_error_responses_never_contain_credentials(server, certificates, caplog, monkeypatch):
    secret = "private password canary"
    with peer(server, certificates) as client:
        success(client.register("Alice", secret))
        reply = client.login("Alice", "wrong " + secret)
        error(reply, ErrorCode.AUTH_FAILED)

        def broken(*args):
            raise RuntimeError(secret + " SECRET_KEY_CANARY")

        monkeypatch.setattr(server.router.auth.passwords, "verify", broken)
        reply = client.login("Alice", secret)
        error(reply, ErrorCode.INTERNAL_ERROR)
        assert secret not in json.dumps(reply)
        assert "SECRET_KEY_CANARY" not in json.dumps(reply)
    assert secret not in caplog.text
    assert "SECRET_KEY_CANARY" not in caplog.text


def test_valid_login_upgrades_old_argon2_parameters(server, certificates):
    old = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1, type=Type.ID).hash(PASSWORD)
    with server.database.connect() as db:
        create_user(db, "Alice", old)
    with peer(server, certificates) as client:
        success(client.login("Alice"))
    with server.database.connect() as db:
        new = find_user_for_login(db, "alice")["password_hash"]
        assert new != old
        assert not PasswordHasher().check_needs_rehash(new)
        assert PasswordHasher().verify(new, PASSWORD)


def test_stalled_plaintext_peer_does_not_block_tls_accepts(server_factory, certificates):
    server = server_factory(limits=replace(ServerLimits(), handshake_timeout=0.4))
    with socket.create_connection(server.address, timeout=3) as stalled:
        with peer(server, certificates) as client:
            success(client.register("Alice"))
        assert stalled.recv(1) == b""


def test_total_frame_timeout_cleans_authenticated_session(server_factory, certificates):
    server = server_factory(limits=replace(ServerLimits(), io_timeout=0.3))
    with peer(server, certificates) as client:
        success(client.register("Alice"))
        success(client.login("Alice"))
        client.online({"Alice"})
        client.transport.socket.sendall(HEADER.pack(100) + b"{")
        wait_until(lambda: server.registry.users() == [])
        assert client.transport.recv_packet() is None


def test_unauthenticated_idle_timeout(server_factory, certificates):
    server = server_factory(limits=replace(ServerLimits(), auth_timeout=0.15))
    with peer(server, certificates) as client:
        assert client.transport.recv_packet() is None


def test_server_stop_cleans_idle_and_authenticated_workers(server, certificates):
    with peer(server, certificates) as client, peer(server, certificates):
        success(client.register("Alice"))
        success(client.login("Alice"))
        client.online({"Alice"})
        server.stop()
        assert server.registry.users() == []
        assert not server._connections
        assert client.transport.recv_packet() is None
        server.stop()  # Idempotent.


def test_authenticated_connection_cannot_register_or_switch_identity(server, certificates):
    with peer(server, certificates) as client:
        user = success(client.register("Alice"))["user"]
        success(client.register("Bob"))
        success(client.login("Alice"))
        error(client.login("Bob"), ErrorCode.ALREADY_LOGGED_IN)
        error(client.register("Carol"), ErrorCode.ALREADY_LOGGED_IN)
        assert success(client.request(RequestType.USERS_LIST))["users"] == [user]


def test_unauthenticated_connection_receives_no_online_events(server, certificates):
    with peer(server, certificates) as outsider, peer(server, certificates) as alice:
        success(outsider.register("Outsider"))
        success(alice.register("Alice"))
        success(alice.login("Alice"))
        alice.online({"Alice"})
        outsider.transport.socket.settimeout(0.15)
        with pytest.raises(TimeoutError):
            outsider.transport.recv_packet()


def test_plaintext_credentials_are_rejected_by_tls_listener(server, certificates):
    with socket.create_connection(server.address, timeout=3) as raw:
        raw.sendall(encode_packet(make_request(RequestType.REGISTER, {
            "username": "Alice", "password": PASSWORD, "confirm_password": PASSWORD,
        })))
        try:
            assert raw.recv(1) == b""
        except ConnectionResetError:
            pass
    with server.database.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    with peer(server, certificates) as client:
        success(client.register("Alice"))


def test_memory_hard_auth_work_is_bounded_and_recovers(server, certificates):
    slots = server.router.auth.hash_slots
    for _ in range(server.limits.hash_workers):
        assert slots.acquire(blocking=False)
    try:
        with peer(server, certificates) as client:
            error(client.register("Alice"), ErrorCode.RATE_LIMITED)
    finally:
        for _ in range(server.limits.hash_workers):
            slots.release()
    with peer(server, certificates) as client:
        success(client.register("Alice"))


def test_connection_capacity_rejects_excess_peer_then_recovers(server_factory, certificates):
    server = server_factory(limits=replace(ServerLimits(), max_connections=1))
    with peer(server, certificates) as client:
        success(client.register("Alice"))
        with socket.create_connection(server.address, timeout=3) as raw:
            assert raw.recv(1) == b""
        success(client.login("Alice"))
    wait_until(lambda: not server._connections)
    with peer(server, certificates) as client:
        success(client.login("Alice"))


def test_continuous_byte_drip_cannot_extend_total_frame_deadline(server_factory, certificates):
    server = server_factory(limits=replace(ServerLimits(), io_timeout=0.25))
    with peer(server, certificates) as client:
        success(client.register("Alice"))
        success(client.login("Alice"))
        client.online({"Alice"})
        client.transport.socket.sendall(HEADER.pack(100))
        for _ in range(8):
            time.sleep(0.05)  # Every write arrives before the per-recv timeout.
            try:
                client.transport.socket.sendall(b" ")
            except OSError:
                break
        assert server.registry.users() == []


def test_concurrent_responses_and_presence_events_keep_one_tls_owner_per_connection(
    server_factory, certificates, monkeypatch,
):
    server = server_factory(limits=replace(ServerLimits(), hash_workers=4))
    owners, lock = {}, threading.Lock()

    def observe(original):
        def wrapped(sock, *args, **kwargs):
            if sock.getsockname()[1] == server.address[1]:
                with lock:
                    owners.setdefault(sock, set()).add(threading.get_ident())
            return original(sock, *args, **kwargs)
        return wrapped

    for method in ("recv", "sendall", "do_handshake"):
        monkeypatch.setattr(ssl.SSLSocket, method, observe(getattr(ssl.SSLSocket, method)))
    barrier = threading.Barrier(3)

    def run(name):
        with peer(server, certificates) as client:
            success(client.register(name))
            barrier.wait(timeout=3)
            success(client.login(name))
            for _ in range(20):
                users = success(client.request(RequestType.USERS_LIST))["users"]
                assert name in {u["username"] for u in users}
            success(client.request(RequestType.LOGOUT))
            revisions = [event["revision"] for event in client.events]
            assert revisions == sorted(set(revisions))

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(run, ("Alice", "Bob", "Carol")))
    wait_until(lambda: not server._connections)
    assert len(owners) == 3
    assert all(len(threads) == 1 for threads in owners.values())


def test_restart_preserves_accounts_but_requires_fresh_login(server, certificates):
    with peer(server, certificates) as client:
        original = success(client.register("Alice"))["user"]
        success(client.login("Alice"))
    server.stop()
    with TLSServer(server.config) as reopened:
        with peer(reopened, certificates) as client:
            error(client.request(RequestType.USERS_LIST), ErrorCode.AUTH_REQUIRED)
            assert success(client.login("ALICE"))["user"] == original


def test_stop_with_incomplete_handshake_and_frame_joins_all_workers(server_factory, certificates):
    server = server_factory(limits=replace(ServerLimits(), handshake_timeout=0.3, io_timeout=0.3))
    with peer(server, certificates) as client, socket.create_connection(server.address, timeout=3):
        client.transport.socket.sendall(HEADER.pack(100) + b"{")
        server.stop()
        assert not server._connections
        assert not server._accept_thread.is_alive()


def test_server_module_entrypoint_serves_tls_auth_and_stops_on_ctrl_c(tmp_path, certificates):
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    environment = os.environ | {
        "STUDYGROUP_HOST": "127.0.0.1", "STUDYGROUP_PORT": str(port),
        "STUDYGROUP_DATA_DIR": str(tmp_path / "cli-data"),
        "STUDYGROUP_TLS_CERT": str(certificates / "server.crt"),
        "STUDYGROUP_TLS_KEY": str(certificates / "server.key"),
    }
    process = subprocess.Popen(
        [sys.executable, "-m", "server.main"], cwd=Path(__file__).resolve().parents[1],
        env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
    )
    try:
        assert select.select([process.stderr], [], [], 10)[0], "Server did not report startup"
        assert "StudyGroup TLS server listening" in process.stderr.readline()
        with connect(ClientConfig("127.0.0.1", port, certificates / "ca.crt"), timeout=3) as transport:
            client = Peer(transport)
            success(client.register("Alice"))
            success(client.login("Alice"))
            client.online({"Alice"})
        process.send_signal(signal.SIGINT)
        assert process.wait(timeout=10) == 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        process.stderr.close()
