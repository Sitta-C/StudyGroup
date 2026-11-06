"""SQLite storage primitives, independent of sockets and authentication.

Database holds only a path; open a separate connection inside each worker.
All writes below use BEGIN IMMEDIATE so join boundaries serialize with sends.
No connection, filesystem or configuration work happens at module import.
"""

import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from server.permissions import (
    AccessDenied,
    VISIBLE_MESSAGES_FROM,
    require_member,
    require_user,
)

SCHEMA_VERSION = 1
BUSY_TIMEOUT_MS = 5000
_USERNAME = re.compile(r"[A-Za-z0-9_]{3,24}\Z", re.ASCII)


def normalize_username(username: str) -> str:
    """ASCII 3–24 letters/digits/underscore; preserve display case separately."""
    if not isinstance(username, str) or not _USERNAME.fullmatch(username):
        raise ValueError("Username must be 3-24 ASCII letters, digits or underscore")
    return username.lower()


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    @contextmanager
    def connect(self):
        """Close on exit; unfinished transactions are rolled back, never committed.

        Uses SQLite's default thread ownership check. Do not share a connection
        across workers or use the sqlite connection context manager to close it.
        """
        conn = sqlite3.connect(self.path, isolation_level=None, timeout=BUSY_TIMEOUT_MS / 1000)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
            yield conn
        finally:
            conn.close()

    def initialize(self) -> None:
        """Create v1 idempotently. Future schema versions need an explicit migration."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        with self.connect() as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, SCHEMA_VERSION):
                raise RuntimeError("Unsupported database schema version")
            conn.execute("PRAGMA journal_mode = WAL")
            try:
                # executescript commits any prior transaction; this connection
                # is fresh and the script explicitly owns BEGIN and COMMIT.
                conn.executescript(
                    "BEGIN IMMEDIATE;\n" + schema
                    + f"\nPRAGMA user_version = {SCHEMA_VERSION};\nCOMMIT;"
                )
            except BaseException:
                if conn.in_transaction:
                    conn.rollback()
                raise


@contextmanager
def transaction(conn: sqlite3.Connection):
    """Commit atomically, rollback on failure; nested calls use savepoints.

    Compose writes with this helper as the outermost transaction too, so the
    write lock is acquired before any reads. Do not wrap in a deferred BEGIN.
    """
    nested = conn.in_transaction
    savepoint = "sp_" + uuid4().hex  # server-generated identifier, never user SQL
    conn.execute(f"SAVEPOINT {savepoint}" if nested else "BEGIN IMMEDIATE")
    try:
        yield
        conn.execute(f"RELEASE SAVEPOINT {savepoint}" if nested else "COMMIT")
    except BaseException:
        if nested:
            conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        elif conn.in_transaction:
            conn.rollback()
        raise


def create_user(conn: sqlite3.Connection, username: str, password_hash: str) -> sqlite3.Row:
    normalized = normalize_username(username)
    if not isinstance(password_hash, str) or not password_hash:
        raise ValueError("Password hash must be nonempty")
    # CP04 must supply an Argon2id hash. This storage API never hashes passwords.
    with transaction(conn):
        user_id = conn.execute(
            "INSERT INTO users (username, username_normalized, password_hash) VALUES (?, ?, ?)",
            (username, normalized, password_hash),
        ).lastrowid
        return conn.execute(
            "SELECT id, username, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()


def find_user_for_login(conn: sqlite3.Connection, username: str) -> sqlite3.Row | None:
    """Internal auth lookup; includes hash and must never be sent to clients."""
    return conn.execute(
        "SELECT * FROM users WHERE username_normalized = ?", (normalize_username(username),)
    ).fetchone()


def create_group(conn: sqlite3.Connection, creator_id: int, name: str) -> sqlite3.Row:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Group name must be nonempty")
    with transaction(conn):
        require_user(conn, creator_id)
        room_id = conn.execute(
            "INSERT INTO rooms (kind, name, created_by) VALUES ('group', ?, ?)",
            (name.strip(), creator_id),
        ).lastrowid
        conn.execute(
            "INSERT INTO room_members (room_id, user_id) VALUES (?, ?)", (room_id, creator_id)
        )
        return conn.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()


def open_private_room(conn: sqlite3.Connection, user_id: int, peer_id: int) -> sqlite3.Row:
    if user_id == peer_id:
        raise ValueError("A private room needs two different users")
    low, high = sorted((user_id, peer_id))
    with transaction(conn):
        require_user(conn, user_id)
        require_user(conn, peer_id)
        conn.execute(
            """INSERT INTO rooms (kind, created_by, private_user_low, private_user_high)
               VALUES ('private', ?, ?, ?)
               ON CONFLICT (private_user_low, private_user_high) DO NOTHING""",
            (user_id, low, high),
        )
        room = conn.execute(
            "SELECT * FROM rooms WHERE private_user_low = ? AND private_user_high = ?",
            (low, high),
        ).fetchone()
        for member in (low, high):
            conn.execute(
                """INSERT INTO room_members (room_id, user_id) VALUES (?, ?)
                   ON CONFLICT (room_id, user_id) DO NOTHING""",
                (room["id"], member),
            )
        return room


def join_group(conn: sqlite3.Connection, user_id: int, room_id: int) -> sqlite3.Row:
    """Self-join only. Repeated joins preserve the original visibility boundary."""
    with transaction(conn):
        require_user(conn, user_id)
        room = conn.execute("SELECT kind FROM rooms WHERE id = ?", (room_id,)).fetchone()
        if room is None or room["kind"] != "group":
            raise AccessDenied()
        conn.execute(
            """INSERT INTO room_members (room_id, user_id, visible_after_message_id)
               SELECT ?, ?, COALESCE(MAX(id), 0) FROM messages WHERE room_id = ?
               ON CONFLICT (room_id, user_id) DO NOTHING""",
            (room_id, user_id, room_id),
        )
        return require_member(conn, user_id, room_id)


def list_groups(conn: sqlite3.Connection, user_id: int) -> list[sqlite3.Row]:
    require_user(conn, user_id)
    return conn.execute(
        "SELECT id, name, created_by, created_at FROM rooms WHERE kind = 'group' ORDER BY id"
    ).fetchall()


def list_group_members(conn: sqlite3.Connection, user_id: int, room_id: int) -> list[sqlite3.Row]:
    require_user(conn, user_id)
    if conn.execute(
        "SELECT 1 FROM rooms WHERE id = ? AND kind = 'group'", (room_id,)
    ).fetchone() is None:
        raise AccessDenied()
    return conn.execute(
        """SELECT u.id, u.username, rm.joined_at FROM room_members AS rm
           JOIN users AS u ON u.id = rm.user_id WHERE rm.room_id = ? ORDER BY u.id""",
        (room_id,),
    ).fetchall()


def add_text_message(conn: sqlite3.Connection, user_id: int, room_id: int, text: str) -> sqlite3.Row:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Message text must be nonempty")
    with transaction(conn):
        require_member(conn, user_id, room_id)
        message_id = conn.execute(
            "INSERT INTO messages (room_id, sender_id, kind, text) VALUES (?, ?, 'text', ?)",
            (room_id, user_id, text),
        ).lastrowid
        return conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()


def get_messages(
    conn: sqlite3.Connection, user_id: int, room_id: int, *,
    before_id: int | None = None, limit: int = 50,
) -> list[sqlite3.Row]:
    """Latest visible page, returned oldest first. Shared basis for history/AI.

    CP07 adds keyword/date search; CP09 must additionally restrict AI to groups
    and cap inputs at 50. No transfer or AI provider is implemented here.
    """
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Limit must be an integer between 1 and 100")
    if before_id is not None and (type(before_id) is not int or before_id <= 0):
        raise ValueError("before_id must be a positive integer")
    require_member(conn, user_id, room_id)
    query = "SELECT m.* " + VISIBLE_MESSAGES_FROM + " AND m.room_id = ?"
    params = [user_id, room_id]
    if before_id is not None:
        query += " AND m.id < ?"
        params.append(before_id)
    query += " ORDER BY m.id DESC LIMIT ?"
    params.append(limit)
    return list(reversed(conn.execute(query, params).fetchall()))
