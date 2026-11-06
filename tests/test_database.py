"""CP03 persistence, constraints, transactions and real SQLite contention."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from threading import Barrier, Event

import pytest

from server.database import (
    Database,
    add_text_message,
    create_group,
    create_user,
    find_user_for_login,
    get_messages,
    join_group,
    normalize_username,
    open_private_room,
    transaction,
)
from server.permissions import AccessDenied


def test_constructing_database_does_not_create_files(tmp_path):
    path = tmp_path / "new-directory" / "studygroup.db"
    assert Database(path).path == path
    assert not path.parent.exists()


def test_initialize_reopen_preserves_all_data(database, conn, users):
    room = create_group(conn, users[0], "วิชาเครือข่าย")
    join_group(conn, users[1], room["id"])
    message = add_text_message(conn, users[0], room["id"], "สวัสดี 👋")
    private = open_private_room(conn, *users[:2])
    with transaction(conn):
        file_id = conn.execute(
            "INSERT INTO messages (room_id, sender_id, kind) VALUES (?, ?, 'file')",
            (room["id"], users[0]),
        ).lastrowid
        conn.execute(
            """INSERT INTO attachments
               (message_id, stored_name, original_name, size_bytes, sha256, status)
               VALUES (?, 'server-token', 'โน้ต.pdf', 3, ?, 'ready')""", (file_id, "a" * 64)
        )
    tables = ("users", "rooms", "room_members", "messages", "attachments")
    def snapshot(connection, table):
        order = "room_id, user_id" if table == "room_members" else "id"
        return [tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY {order}")]
    snapshots = {table: snapshot(conn, table) for table in tables}
    reopened = Database(database.path)
    reopened.initialize()
    reopened.initialize()
    with reopened.connect() as other:
        assert other.execute("PRAGMA user_version").fetchone()[0] == 1
        assert other.execute("PRAGMA foreign_key_check").fetchall() == []
        assert other.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        for table in tables:
            assert snapshot(other, table) == snapshots[table]
        assert get_messages(other, users[1], room["id"])[0]["id"] == message["id"]
        assert open_private_room(other, users[1], users[0])["id"] == private["id"]


def test_connection_settings_and_close(database):
    with database.connect() as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")


def test_connection_cannot_cross_threads(conn):
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(conn.execute, "SELECT 1")
        with pytest.raises(sqlite3.ProgrammingError, match="same thread"):
            future.result(timeout=5)


def test_unfinished_transaction_is_rolled_back_on_close(database):
    with database.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        create_user(connection, "Alice", "hash")
    with database.connect() as connection:
        assert connection.execute("SELECT count(*) FROM users").fetchone()[0] == 0


def test_unsupported_version_is_untouched(database, conn, users):
    conn.execute("PRAGMA user_version = 99")
    with pytest.raises(RuntimeError, match="schema version"):
        database.initialize()
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 99
    assert conn.execute("SELECT count(*) FROM users").fetchone()[0] == len(users)


def test_schema_error_rolls_back_entire_initialization(tmp_path, monkeypatch):
    original_read = Path.read_text
    def invalid_schema(path, *args, **kwargs):
        return original_read(path, *args, **kwargs) + "\nTHIS IS INVALID SQL;"
    monkeypatch.setattr(Path, "read_text", invalid_schema)
    db = Database(tmp_path / "broken.db")
    with pytest.raises(sqlite3.OperationalError):
        db.initialize()
    with db.connect() as connection:
        assert connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall() == []
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 0


@pytest.mark.parametrize("name", ["Alice", "a_1", "Z" * 24])
def test_username_case_preserved_and_login_normalized(conn, name):
    user = create_user(conn, name, "hash")
    assert user["username"] == name
    assert "password_hash" not in user.keys()
    found = find_user_for_login(conn, name.swapcase())
    assert found["id"] == user["id"]
    assert found["username_normalized"] == name.lower()
    assert found["password_hash"] == "hash"
    assert find_user_for_login(conn, "missing") is None
    with pytest.raises(sqlite3.IntegrityError):
        create_user(conn, name.swapcase(), "other-hash")


@pytest.mark.parametrize("name", [None, 123, "", "ab", "a" * 25, " Alice", "Alice ", "a-b", "ชื่อไทย", "Ａlice", "abc\n", "abc\x00def", "a' OR 1=1--"])
def test_invalid_username(name):
    with pytest.raises(ValueError):
        normalize_username(name)


def test_normalization_is_enforced_by_database(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO users (username, username_normalized, password_hash) VALUES ('Alice', 'ALICE', 'hash')"
        )
    create_user(conn, "Alice", "hash")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO users (username, username_normalized, password_hash) VALUES ('ALICE', 'alice', 'hash')"
        )


@pytest.mark.parametrize("name", ["ab", "a" * 25, "a-b", "ชื่อไทย", "abc\x00def"])
def test_username_format_is_enforced_by_database(conn, name):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO users (username, username_normalized, password_hash) VALUES (?, ?, 'hash')",
            (name, name.lower()),
        )


@pytest.mark.parametrize("password_hash", [None, "", 12])
def test_empty_or_nonstring_hash_rejected(conn, password_hash):
    with pytest.raises(ValueError):
        create_user(conn, "Alice", password_hash)


def test_group_and_private_membership_invariants(conn, users):
    alice, bob, carol = users
    group = create_group(conn, alice, "  Network  ")
    assert group["name"] == "Network"
    assert [r[0] for r in conn.execute("SELECT user_id FROM room_members")] == [alice]
    private = open_private_room(conn, alice, bob)
    assert open_private_room(conn, bob, alice)["id"] == private["id"]
    assert [tuple(r) for r in conn.execute(
        "SELECT user_id, visible_after_message_id FROM room_members WHERE room_id = ? ORDER BY user_id",
        (private["id"],),
    )] == [(alice, 0), (bob, 0)]
    for member, boundary in ((carol, 0), (alice, 10)):
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT OR REPLACE INTO room_members (room_id, user_id, visible_after_message_id) VALUES (?, ?, ?)",
                (private["id"], member, boundary),
            )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE room_members SET user_id = ? WHERE room_id = ? AND user_id = ?",
                     (carol, private["id"], bob))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO rooms (kind, created_by, private_user_low, private_user_high) VALUES ('private', ?, ?, ?)",
            (alice, alice, bob),
        )
    with pytest.raises(ValueError):
        open_private_room(conn, alice, alice)
    with pytest.raises(AccessDenied):
        open_private_room(conn, alice, 9999)


@pytest.mark.parametrize("values", [
    ("invalid", "name", 1, None, None),
    ("private", None, 1, 2, 1),
    ("private", None, 1, 1, 1),
    ("private", None, 1, None, 2),
    ("private", "name", 1, 1, 2),
    ("private", None, 3, 1, 2),
    ("group", None, 1, None, None),
    ("group", "", 1, None, None),
    ("group", "name", 1, 1, 2),
])
def test_invalid_room_shapes(conn, users, values):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO rooms (kind, name, created_by, private_user_low, private_user_high) VALUES (?, ?, ?, ?, ?)",
            values,
        )


def test_foreign_keys_and_message_constraints(conn, users):
    room = create_group(conn, users[0], "Network")["id"]
    for sql, params in [
        ("INSERT INTO room_members (room_id, user_id) VALUES (?, ?)", (9999, users[0])),
        ("INSERT INTO room_members (room_id, user_id) VALUES (?, ?)", (room, 9999)),
        ("INSERT INTO room_members (room_id, user_id) VALUES (?, ?)", (room, users[0])),
        ("INSERT INTO messages (room_id, sender_id, kind, text) VALUES (?, ?, 'text', 'x')", (room, users[1])),
        ("INSERT INTO messages (room_id, sender_id, kind, text) VALUES (?, ?, 'text', NULL)", (room, users[0])),
        ("INSERT INTO messages (room_id, sender_id, kind, text) VALUES (?, ?, 'text', '')", (room, users[0])),
        ("INSERT INTO messages (room_id, sender_id, kind, text) VALUES (?, ?, 'file', 'x')", (room, users[0])),
        ("INSERT INTO messages (room_id, sender_id, kind, text) VALUES (?, ?, 'other', 'x')", (room, users[0])),
        ("UPDATE room_members SET visible_after_message_id = -1 WHERE room_id = ?", (room,)),
    ]:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(sql, params)
    message = add_text_message(conn, users[0], room, "saved")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM users WHERE id = ?", (users[0],))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM room_members WHERE room_id = ?", (room,))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE messages SET sender_id = ? WHERE id = ?", (users[1], message["id"]))


def test_utc_timestamps_and_committed_ids_are_never_reused(conn, users):
    group = create_group(conn, users[0], "Network")
    member = join_group(conn, users[1], group["id"])
    first = add_text_message(conn, users[0], group["id"], "one")
    for timestamp in (find_user_for_login(conn, "Alice")["created_at"], group["created_at"],
                      member["joined_at"], first["created_at"]):
        assert timestamp.endswith("Z")
        assert datetime.fromisoformat(timestamp).utcoffset() == timedelta(0)
    conn.execute("DELETE FROM messages WHERE id = ?", (first["id"],))
    assert add_text_message(conn, users[0], group["id"], "two")["id"] > first["id"]


def test_parameterized_queries_keep_sql_as_data(conn, users):
    text = "'); DROP TABLE users; -- สวัสดี 👋"
    group = create_group(conn, users[0], text)
    message = add_text_message(conn, users[0], group["id"], text)
    assert group["name"] == text
    assert get_messages(conn, users[0], group["id"])[0]["text"] == text
    assert message["text"] == text
    assert conn.execute("SELECT count(*) FROM users").fetchone()[0] == 3


def test_creation_and_join_rollback_on_injected_failure(conn, users):
    conn.executescript("""
        CREATE TEMP TRIGGER fail_membership AFTER INSERT ON room_members
        BEGIN SELECT RAISE(ABORT, 'injected failure'); END;
    """)
    for create in (lambda: create_group(conn, users[0], "Network"),
                   lambda: open_private_room(conn, *users[:2])):
        with pytest.raises(sqlite3.IntegrityError, match="injected"):
            create()
        assert conn.execute("SELECT count(*) FROM rooms").fetchone()[0] == 0
    conn.execute("DROP TRIGGER fail_membership")
    room = create_group(conn, users[0], "Network")["id"]
    conn.executescript("""
        CREATE TEMP TRIGGER fail_join AFTER INSERT ON room_members
        BEGIN SELECT RAISE(ABORT, 'injected failure'); END;
    """)
    with pytest.raises(sqlite3.IntegrityError):
        join_group(conn, users[1], room)
    assert conn.execute("SELECT count(*) FROM room_members").fetchone()[0] == 1
    assert not conn.in_transaction


def test_nested_transactions_and_rollback(conn, users):
    with pytest.raises(RuntimeError, match="rollback"):
        with transaction(conn):
            room = create_group(conn, users[0], "Network")["id"]
            add_text_message(conn, users[0], room, "never published")
            raise RuntimeError("rollback")
    assert conn.execute("SELECT count(*) FROM rooms").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM messages").fetchone()[0] == 0
    with transaction(conn):
        create_user(conn, "Dave", "hash")
        with pytest.raises(sqlite3.IntegrityError):
            create_user(conn, "DAVE", "hash")
        create_user(conn, "Erin", "hash")
    assert find_user_for_login(conn, "Dave") is not None
    assert find_user_for_login(conn, "Erin") is not None
    assert not conn.in_transaction


def test_concurrent_private_room_and_join_are_unique(database, conn, users):
    room = create_group(conn, users[0], "Network")["id"]
    boundary = add_text_message(conn, users[0], room, "old")["id"]
    barrier = Barrier(6)
    def worker(index):
        with database.connect() as connection:
            barrier.wait(timeout=5)
            pair = users[:2] if index % 2 else users[1::-1]
            private = open_private_room(connection, *pair)
            member = join_group(connection, users[2], room)
            return private["id"], member["visible_after_message_id"]
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(worker, range(6)))
    assert len(set(results)) == 1
    assert results[0][1] == boundary
    assert conn.execute("SELECT count(*) FROM rooms WHERE kind = 'private'").fetchone()[0] == 1
    assert conn.execute("SELECT count(*) FROM room_members WHERE room_id = ?", (room,)).fetchone()[0] == 2


def test_concurrent_normalized_usernames_have_one_winner(database, conn):
    barrier = Barrier(2)
    def register(name):
        with database.connect() as connection:
            barrier.wait(timeout=5)
            try:
                return create_user(connection, name, "hash")["id"]
            except sqlite3.IntegrityError:
                assert not connection.in_transaction
                return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(register, ("Alice", "ALICE")))
    assert sum(result is not None for result in results) == 1
    assert conn.execute("SELECT count(*) FROM users").fetchone()[0] == 1


@pytest.mark.parametrize("first_operation", ["send", "join"])
def test_join_boundary_serializes_with_sends(database, conn, users, first_operation):
    room = create_group(conn, users[0], "Network")["id"]
    old = add_text_message(conn, users[0], room, "old")["id"]
    attempting = Event()
    def second_operation():
        with database.connect() as connection:
            def trace(sql):
                if sql == "BEGIN IMMEDIATE":
                    attempting.set()
            connection.set_trace_callback(trace)
            if first_operation == "send":
                return join_group(connection, users[1], room)["visible_after_message_id"]
            return add_text_message(connection, users[0], room, "after join")["id"]
    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction(conn):
            if first_operation == "send":
                latest = add_text_message(conn, users[0], room, "before join")["id"]
            else:
                assert join_group(conn, users[1], room)["visible_after_message_id"] == old
            future = pool.submit(second_operation)
            assert attempting.wait(timeout=5)
            assert not future.done()  # second connection is blocked on our write lock
        result = future.result(timeout=5)
    visible = get_messages(conn, users[1], room)
    if first_operation == "send":
        assert result == latest
        assert visible == []
    else:
        assert [row["id"] for row in visible] == [result]
