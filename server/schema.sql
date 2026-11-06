-- Schema v1. Initialization owns the transaction; no runtime data is seeded.
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL CHECK (
        length(username) BETWEEN 3 AND 24
        AND username NOT GLOB '*[^A-Za-z0-9_]*'
        AND instr(username, char(0)) = 0
    ),
    username_normalized TEXT NOT NULL UNIQUE
        CHECK (username_normalized = lower(username)),
    password_hash TEXT NOT NULL CHECK (length(password_hash) > 0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
) STRICT;

CREATE TABLE IF NOT EXISTS rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL CHECK (kind IN ('private', 'group')),
    name TEXT,
    created_by INTEGER NOT NULL REFERENCES users(id),
    private_user_low INTEGER REFERENCES users(id),
    private_user_high INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (
        (kind = 'group' AND name IS NOT NULL AND length(trim(name)) > 0
         AND private_user_low IS NULL AND private_user_high IS NULL)
        OR
        (kind = 'private' AND name IS NULL
         AND private_user_low IS NOT NULL AND private_user_high IS NOT NULL
         AND private_user_low < private_user_high
         AND created_by IN (private_user_low, private_user_high))
    ),
    UNIQUE (private_user_low, private_user_high)
) STRICT;

CREATE TABLE IF NOT EXISTS room_members (
    room_id INTEGER NOT NULL REFERENCES rooms(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    joined_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    visible_after_message_id INTEGER NOT NULL DEFAULT 0
        CHECK (visible_after_message_id >= 0),
    PRIMARY KEY (room_id, user_id)
) STRICT;

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id INTEGER NOT NULL REFERENCES rooms(id),
    sender_id INTEGER NOT NULL REFERENCES users(id),
    kind TEXT NOT NULL CHECK (kind IN ('text', 'file')),
    text TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (room_id, sender_id) REFERENCES room_members(room_id, user_id),
    CHECK ((kind = 'text' AND text IS NOT NULL AND length(trim(text)) > 0)
           OR (kind = 'file' AND text IS NULL))
) STRICT;

CREATE TABLE IF NOT EXISTS attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL UNIQUE REFERENCES messages(id),
    stored_name TEXT NOT NULL UNIQUE CHECK (
        length(stored_name) > 0 AND stored_name NOT IN ('.', '..')
        AND instr(stored_name, '/') = 0 AND instr(stored_name, char(92)) = 0
        AND instr(stored_name, char(0)) = 0
    ),
    original_name TEXT NOT NULL CHECK (length(original_name) > 0),
    size_bytes INTEGER NOT NULL CHECK (size_bytes BETWEEN 0 AND 5242880),
    sha256 TEXT NOT NULL CHECK (
        length(sha256) = 64 AND sha256 NOT GLOB '*[^0-9a-f]*'
        AND instr(sha256, char(0)) = 0
    ),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'ready', 'failed'))
) STRICT;

CREATE INDEX IF NOT EXISTS room_members_by_user ON room_members(user_id, room_id);
CREATE INDEX IF NOT EXISTS messages_by_room_id ON messages(room_id, id);
CREATE INDEX IF NOT EXISTS messages_by_room_date ON messages(room_id, created_at, id);
CREATE INDEX IF NOT EXISTS rooms_by_kind ON rooms(kind, id);

CREATE TRIGGER IF NOT EXISTS private_member_insert
BEFORE INSERT ON room_members
WHEN EXISTS (
    SELECT 1 FROM rooms WHERE id = NEW.room_id AND kind = 'private'
    AND (NEW.user_id NOT IN (private_user_low, private_user_high)
         OR NEW.visible_after_message_id != 0)
)
BEGIN
    SELECT RAISE(ABORT, 'invalid private membership');
END;

CREATE TRIGGER IF NOT EXISTS private_member_update
BEFORE UPDATE ON room_members
WHEN EXISTS (
    SELECT 1 FROM rooms WHERE id = NEW.room_id AND kind = 'private'
    AND (NEW.user_id NOT IN (private_user_low, private_user_high)
         OR NEW.visible_after_message_id != 0)
)
BEGIN
    SELECT RAISE(ABORT, 'invalid private membership');
END;

CREATE TRIGGER IF NOT EXISTS attachment_file_insert
BEFORE INSERT ON attachments
WHEN (SELECT kind FROM messages WHERE id = NEW.message_id) != 'file'
BEGIN
    SELECT RAISE(ABORT, 'attachment requires a file message');
END;

CREATE TRIGGER IF NOT EXISTS attachment_file_update
BEFORE UPDATE OF message_id ON attachments
WHEN (SELECT kind FROM messages WHERE id = NEW.message_id) != 'file'
BEGIN
    SELECT RAISE(ABORT, 'attachment requires a file message');
END;
