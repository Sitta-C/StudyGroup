"""Shared data authorization. user_id must come from the authenticated session.

Group/member listings are public to registered users; content is member-only.
Missing and inaccessible content have the same error to avoid ID probing.
"""

import sqlite3

from shared.message_types import ErrorCode


class AccessDenied(PermissionError):
    code = ErrorCode.FORBIDDEN

    def __init__(self):
        super().__init__("Access to this content is forbidden")


# Use this join for history, search, file access and future AI inputs. The pair
# check also fails closed if a private membership was corrupted by manual SQL.
VISIBLE_MESSAGES_FROM = """
    FROM messages AS m
    LEFT JOIN attachments AS a ON a.message_id = m.id
    JOIN room_members AS rm ON rm.room_id = m.room_id AND rm.user_id = ?
    JOIN rooms AS r ON r.id = m.room_id
    WHERE m.id > rm.visible_after_message_id
      AND (r.kind = 'group' OR rm.user_id IN (r.private_user_low, r.private_user_high))
      AND (m.kind = 'text' OR a.status = 'ready')
"""


def require_user(conn: sqlite3.Connection, user_id: int) -> None:
    if conn.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone() is None:
        raise AccessDenied()


def require_member(conn: sqlite3.Connection, user_id: int, room_id: int) -> sqlite3.Row:
    row = conn.execute(
        """SELECT rm.*, r.kind FROM room_members AS rm
           JOIN rooms AS r ON r.id = rm.room_id
           WHERE rm.user_id = ? AND rm.room_id = ?
             AND (r.kind = 'group' OR rm.user_id IN (r.private_user_low, r.private_user_high))""",
        (user_id, room_id),
    ).fetchone()
    if row is None:
        raise AccessDenied()
    return row


def require_message(conn: sqlite3.Connection, user_id: int, message_id: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT m.* " + VISIBLE_MESSAGES_FROM + " AND m.id = ?",
        (user_id, message_id),
    ).fetchone()
    if row is None:
        raise AccessDenied()
    return row


def require_attachment(conn: sqlite3.Connection, user_id: int, attachment_id: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT a.*, m.room_id "
        + VISIBLE_MESSAGES_FROM
        + " AND a.id = ? AND a.status = 'ready'",
        (user_id, attachment_id),
    ).fetchone()
    if row is None:
        raise AccessDenied()
    return row
