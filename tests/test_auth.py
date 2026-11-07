"""Authentication invariants independent of the transport."""

from concurrent.futures import ThreadPoolExecutor
import threading

from argon2 import PasswordHasher, Type
import pytest

from server.passwords import Passwords, validate_password
from server.rate_limit import AuthRateLimiter
from server.connection import ClientConnection
from server.main import ServerLimits
from server.sessions import SessionRegistry
from shared.protocol import make_response


@pytest.fixture(scope="module")
def passwords():
    return Passwords()


def test_passwords_use_argon2id_and_random_salt(passwords):
    secret = "ทดสอบ🔑 password"
    first, second = passwords.hash(secret), passwords.hash(secret)
    assert first.startswith("$argon2id$")
    assert first != second
    assert passwords.verify(first, secret)
    assert not passwords.verify(first, secret.upper())
    assert not passwords.verify(None, secret)
    assert not passwords.verify("corrupt hash", secret)


@pytest.mark.parametrize("value", [None, 123, True, "", "1234567", "a" * 129, "abcd\x00efgh"])
def test_password_policy_rejects_invalid_input(value):
    with pytest.raises(ValueError):
        validate_password(value)


@pytest.mark.parametrize("value", ["12345678", " " * 8, "ก" * 128, "🔑" * 128])
def test_password_policy_preserves_valid_input(value):
    assert validate_password(value) == value


def test_password_spaces_and_unicode_are_not_normalized(passwords):
    secret = "  Café password  "
    hashed = passwords.hash(secret)
    assert passwords.verify(hashed, secret)
    assert not passwords.verify(hashed, secret.strip())
    assert not passwords.verify(hashed, "  Cafe\u0301 password  ")


def test_hash_upgrade_is_detected(passwords):
    old = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1, type=Type.ID)
    hashed = old.hash("old password")
    assert passwords.verify(hashed, "old password")
    assert passwords.hasher.check_needs_rehash(hashed)


class QueuedConnection:
    def __init__(self):
        self.user = None
        self.packets = []
        self.closed = False

    def enqueue(self, packet):
        self.packets.append(packet)
        return True

    def request_close(self):
        self.closed = True


def test_concurrent_resume_has_one_owner_and_stale_logout_cannot_revoke_token():
    registry = SessionRegistry(resume_ttl=60, clock=lambda: 100)
    user = {"id": 1, "username": "Alice"}
    old = QueuedConnection()
    assert registry.login(old, user, make_response("login", {"user": user}))
    remembered = old.packets[0]["data"]["result"]
    peers = [QueuedConnection() for _ in range(8)]
    barrier = threading.Barrier(len(peers))

    def resume(peer):
        barrier.wait(timeout=5)
        return registry.resume(peer, remembered["resume_token"], "resume")

    with ThreadPoolExecutor(max_workers=len(peers)) as pool:
        assert all(pool.map(resume, peers))
    live = [peer for peer in peers if not peer.closed]
    assert len(live) == 1
    assert registry.users() == [user]
    assert old.closed and old.user is None
    assert all(peer.packets[0]["data"]["result"] == remembered for peer in peers)
    # Both ordinary cleanup and a queued logout from an obsolete owner are harmless.
    for stale in [old, *(peer for peer in peers if peer.closed)]:
        stale.user = dict(user)
        assert not registry.logout(stale, make_response("late-logout", {}))
    latest = QueuedConnection()
    assert registry.resume(latest, remembered["resume_token"], "again")
    assert live[0].closed
    assert registry.logout(latest, make_response("logout", {}))
    assert not registry.resume(QueuedConnection(), remembered["resume_token"], "revoked")


def test_failed_resume_queue_leaves_existing_connection_and_token_intact():
    registry = SessionRegistry(resume_ttl=60, clock=lambda: 100)
    user = {"id": 1, "username": "Alice"}
    old = QueuedConnection()
    assert registry.login(old, user, make_response("login", {"user": user}))
    token = old.packets[0]["data"]["result"]["resume_token"]
    failed = QueuedConnection()
    failed.enqueue = lambda _: False
    assert not registry.resume(failed, token, "failed")
    assert failed.user is None and old.user == user and not old.closed
    assert registry.resume(QueuedConnection(), token, "working")


def test_registry_atomic_duplicate_login_and_stale_cleanup():
    registry = SessionRegistry()
    peers = [QueuedConnection() for _ in range(8)]
    user = {"id": 1, "username": "Alice"}
    barrier = threading.Barrier(len(peers))

    def login(peer):
        barrier.wait(timeout=5)
        return registry.login(peer, user, make_response("login", {"user": user}))

    with ThreadPoolExecutor(max_workers=len(peers)) as pool:
        results = list(pool.map(login, peers))
    assert sum(results) == 1
    old = peers[results.index(True)]
    assert old.packets[0]["type"] == "RESPONSE"
    assert old.packets[1]["data"]["users"] == [user]
    assert registry.logout(old)
    fresh = QueuedConnection()
    assert registry.login(fresh, user, make_response("new", {}))
    # Model a delayed cleanup still holding the old identity.
    old.user = dict(user)
    assert not registry.logout(old)
    assert registry.users() == [user]
    assert fresh.user == user
    assert not registry.logout(old)


def test_registry_events_are_ordered_and_only_include_logged_in_users():
    registry = SessionRegistry()
    alice, bob = QueuedConnection(), QueuedConnection()
    for index, peer in enumerate((alice, bob), 1):
        assert registry.login(peer, {"id": index, "username": f"User{index}"}, make_response("l", {}))
    assert registry.logout(bob, make_response("logout", {}))
    for peer in (alice, bob):
        events = [p for p in peer.packets if p["type"] == "USERS_UPDATED"]
        revisions = [p["data"]["revision"] for p in events]
        assert revisions == sorted(set(revisions))
        assert events[-1]["data"]["users"] == [{"id": 1, "username": "User1"}]
    assert bob.user is None


def test_rate_limit_shared_across_addresses_normalized_account_and_window():
    now = [0.0]
    limiter = AuthRateLimiter(address_limit=3, account_limit=2, window=10, clock=lambda: now[0])
    assert limiter.allow("ip1", "alice")
    assert limiter.allow("ip2", "alice")
    assert not limiter.allow("ip3", "alice")
    assert limiter.allow("ip1", "bob")
    assert limiter.allow("ip1", "carol")
    assert not limiter.allow("ip1", "dave")
    now[0] = 10.0
    assert limiter.allow("ip1", "alice")


def test_rate_limit_fails_closed_at_capacity_and_expires():
    now = [0.0]
    limiter = AuthRateLimiter(max_keys=2, window=5, clock=lambda: now[0])
    assert limiter.allow("ip", "alice")
    assert not limiter.allow("other", "bob")
    now[0] = 5.0
    assert limiter.allow("other", "bob")


def test_slow_connection_outbox_is_bounded_and_does_not_block_presence():
    import socket
    from types import SimpleNamespace

    registry = SessionRegistry()
    with socket.socket() as raw:
        slow = ClientConnection(raw, ("127.0.0.1", 1), SimpleNamespace(limits=ServerLimits(outbox_size=2)))
        try:
            assert registry.login(slow, {"id": 1, "username": "Alice"}, make_response("login", {}))
            # Login response and presence fill the queue. A new event must drop
            # the slow connection, without blocking another user's login.
            healthy = QueuedConnection()
            assert registry.login(healthy, {"id": 2, "username": "Bob"}, make_response("login2", {}))
            assert slow._stopping.is_set()
            assert slow._outbox.qsize() == 2
            registry.logout(slow)
            assert registry.users() == [{"id": 2, "username": "Bob"}]
            assert healthy.packets[-1]["data"]["users"] == registry.users()
        finally:
            slow._wake_read.close()
            slow._wake_write.close()
