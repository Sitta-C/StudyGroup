"""Authorization matrix for members, outsiders and post-join content."""

import sqlite3

import pytest

from server.database import (
    add_text_message, create_group, get_messages, join_group,
    list_group_members, list_groups, open_private_room, transaction,
)
from server.permissions import (
    AccessDenied, require_attachment, require_member, require_message,
)
from shared.message_types import ErrorCode


def file_record(conn, room_id, sender_id, *, status="ready", **overrides):
    """Metadata fixture only; CP08 must verify actual bytes/hash before ready."""
    with transaction(conn):
        message_id = conn.execute(
            "INSERT INTO messages (room_id, sender_id, kind) VALUES (?, ?, 'file')",
            (room_id, sender_id),
        ).lastrowid
        values = dict(stored_name=f"server-{message_id}", original_name="โน้ต.pdf",
                      size_bytes=5, sha256="a" * 64)
        values.update(overrides)
        attachment_id = conn.execute(
            """INSERT INTO attachments
               (message_id, stored_name, original_name, size_bytes, sha256, status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (message_id, values["stored_name"], values["original_name"], values["size_bytes"], values["sha256"], status),
        ).lastrowid
        return message_id, attachment_id


def test_private_pair_only(conn, users):
    alice, bob, carol = users
    room = open_private_room(conn, alice, bob)["id"]
    message = add_text_message(conn, alice, room, "private")["id"]
    file_message, attachment = file_record(conn, room, alice)
    for user in (alice, bob):
        assert require_member(conn, user, room)["visible_after_message_id"] == 0
        assert require_message(conn, user, message)["text"] == "private"
        assert require_attachment(conn, user, attachment)["message_id"] == file_message
        assert [row["id"] for row in get_messages(conn, user, room)] == [message, file_message]
    for operation in (
        lambda: require_member(conn, carol, room),
        lambda: require_message(conn, carol, message),
        lambda: require_attachment(conn, carol, attachment),
        lambda: get_messages(conn, carol, room),
        lambda: add_text_message(conn, carol, room, "unauthorized"),
        lambda: join_group(conn, carol, room),
        lambda: list_group_members(conn, carol, room),
    ):
        with pytest.raises(AccessDenied) as caught:
            operation()
        assert caught.value.code == ErrorCode.FORBIDDEN
    assert list_groups(conn, carol) == []


def test_group_metadata_public_content_private(conn, users):
    alice, bob, _ = users
    room = create_group(conn, alice, "Network")["id"]
    add_text_message(conn, alice, room, "secret")
    assert [row["id"] for row in list_groups(conn, bob)] == [room]
    members = list_group_members(conn, bob, room)
    assert [row["id"] for row in members] == [alice]
    assert set(members[0].keys()) == {"id", "username", "joined_at"}
    with pytest.raises(AccessDenied):
        get_messages(conn, bob, room)
    with pytest.raises(AccessDenied):
        add_text_message(conn, bob, room, "blocked")
    with pytest.raises(AccessDenied):
        list_groups(conn, 9999)
    with pytest.raises(AccessDenied):
        list_group_members(conn, 9999, room)


def test_new_member_boundary_applies_to_text_files_and_future_ai_input(conn, users):
    alice, bob, carol = users
    room = create_group(conn, alice, "Network")["id"]
    old_text = add_text_message(conn, alice, room, "before join")["id"]
    old_file, old_attachment = file_record(conn, room, alice)
    # An unrelated room's higher ID must not define this room's boundary.
    other = create_group(conn, alice, "Other")["id"]
    other_message = add_text_message(conn, alice, other, "other room")["id"]
    member = join_group(conn, bob, room)
    assert member["visible_after_message_id"] == old_file < other_message
    assert get_messages(conn, bob, room) == []
    new_text = add_text_message(conn, bob, room, "after join")["id"]
    new_file, new_attachment = file_record(conn, room, alice)
    assert join_group(conn, bob, room)["visible_after_message_id"] == old_file
    assert join_group(conn, alice, room)["visible_after_message_id"] == 0
    assert [row["id"] for row in get_messages(conn, alice, room)] == [old_text, old_file, new_text, new_file]
    assert [row["id"] for row in get_messages(conn, bob, room)] == [new_text, new_file]
    assert require_message(conn, bob, new_text)["sender_id"] == bob
    assert require_attachment(conn, bob, new_attachment)["room_id"] == room
    for user, target in ((bob, old_text), (bob, old_file), (bob, other_message), (carol, new_text)):
        with pytest.raises(AccessDenied):
            require_message(conn, user, target)
    for user, target in ((bob, old_attachment), (carol, new_attachment)):
        with pytest.raises(AccessDenied):
            require_attachment(conn, user, target)
    assert get_messages(conn, bob, room, before_id=new_text) == []


def test_join_empty_group_starts_at_zero(conn, users):
    room = create_group(conn, users[0], "Network")["id"]
    assert join_group(conn, users[1], room)["visible_after_message_id"] == 0
    message = add_text_message(conn, users[0], room, "first")["id"]
    assert require_message(conn, users[1], message)["id"] == message


@pytest.mark.parametrize("status", ["pending", "failed"])
def test_unpublished_attachments_and_messages_are_hidden(conn, users, status):
    room = create_group(conn, users[0], "Network")["id"]
    message, attachment = file_record(conn, room, users[0], status=status)
    assert get_messages(conn, users[0], room) == []
    with pytest.raises(AccessDenied):
        require_message(conn, users[0], message)
    with pytest.raises(AccessDenied):
        require_attachment(conn, users[0], attachment)
    join_group(conn, users[1], room)
    conn.execute("UPDATE attachments SET status = 'ready' WHERE id = ?", (attachment,))
    assert require_attachment(conn, users[0], attachment)["status"] == "ready"
    # Publishing an older pending transfer cannot bypass the join boundary.
    with pytest.raises(AccessDenied):
        require_attachment(conn, users[1], attachment)


def test_file_message_without_attachment_is_hidden(conn, users):
    room = create_group(conn, users[0], "Network")["id"]
    message = conn.execute(
        "INSERT INTO messages (room_id, sender_id, kind) VALUES (?, ?, 'file')", (room, users[0])
    ).lastrowid
    assert get_messages(conn, users[0], room) == []
    with pytest.raises(AccessDenied):
        require_message(conn, users[0], message)


@pytest.mark.parametrize("overrides", [
    {"size_bytes": -1}, {"size_bytes": 5242881}, {"size_bytes": 1.5},
    {"sha256": "abc"}, {"sha256": "A" * 64}, {"sha256": "z" * 64},
    {"sha256": "a" * 64 + "\x00suffix"},
    {"stored_name": "../secret"}, {"stored_name": "a/b"}, {"stored_name": "a\\b"},
    {"stored_name": ".."}, {"stored_name": ""}, {"stored_name": "file\x00suffix"},
    {"original_name": ""},
])
def test_attachment_constraints_and_atomic_rollback(conn, users, overrides):
    room = create_group(conn, users[0], "Network")["id"]
    with pytest.raises(sqlite3.IntegrityError):
        file_record(conn, room, users[0], **overrides)
    assert conn.execute("SELECT count(*) FROM messages").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM attachments").fetchone()[0] == 0


def test_attachment_foreign_key_kind_unique_and_status(conn, users):
    room = create_group(conn, users[0], "Network")["id"]
    message, attachment = file_record(conn, room, users[0], size_bytes=5242880)
    text = add_text_message(conn, users[0], room, "text")["id"]
    for target in (message, text, 9999):
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO attachments (message_id, stored_name, original_name, size_bytes, sha256)
                   VALUES (?, 'other-token', 'file', 0, ?)""", (target, "a" * 64)
            )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE attachments SET message_id = ? WHERE id = ?", (text, attachment))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE attachments SET status = 'invalid' WHERE id = ?", (attachment,))
    with pytest.raises(sqlite3.IntegrityError):
        file_record(conn, room, users[0], stored_name=f"server-{message}")


def test_pagination_is_stable_and_ordered(conn, users):
    room = create_group(conn, users[0], "Network")["id"]
    ids = [add_text_message(conn, users[0], room, str(i))["id"] for i in range(7)]
    latest = get_messages(conn, users[0], room, limit=3)
    earlier = get_messages(conn, users[0], room, before_id=latest[0]["id"], limit=3)
    assert [row["id"] for row in latest] == ids[4:]
    assert [row["id"] for row in earlier] == ids[1:4]
    assert [row["id"] for row in get_messages(conn, users[0], room, before_id=earlier[0]["id"], limit=3)] == ids[:1]


@pytest.mark.parametrize("kwargs", [{"limit": 0}, {"limit": 101}, {"limit": True},
                                    {"limit": "50"}, {"before_id": 0}, {"before_id": True},
                                    {"before_id": "1 OR 1=1"}])
def test_invalid_pagination(conn, users, kwargs):
    room = create_group(conn, users[0], "Network")["id"]
    with pytest.raises(ValueError):
        get_messages(conn, users[0], room, **kwargs)


def test_missing_ids_fail_closed(conn, users):
    for operation in (
        lambda: require_member(conn, users[0], 9999),
        lambda: require_message(conn, users[0], 9999),
        lambda: require_attachment(conn, users[0], 9999),
        lambda: join_group(conn, users[0], 9999),
        lambda: list_group_members(conn, users[0], 9999),
    ):
        with pytest.raises(AccessDenied):
            operation()
