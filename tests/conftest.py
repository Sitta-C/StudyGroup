"""Storage fixtures use a temporary on-disk database, never data/ or .env."""

import pytest

from server.database import Database, create_user


@pytest.fixture
def database(tmp_path):
    db = Database(tmp_path / "ข้อมูล" / "studygroup.db")
    db.initialize()
    return db


@pytest.fixture
def conn(database):
    with database.connect() as connection:
        yield connection


@pytest.fixture
def users(conn):
    # Opaque storage fixtures, not plaintext passwords or CP04 auth evidence.
    return [create_user(conn, name, "test-hash")["id"] for name in ("Alice", "Bob", "Carol")]
