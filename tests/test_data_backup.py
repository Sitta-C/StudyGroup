"""CP10: committed WAL snapshots, complete restores, corruption and safe paths."""

import hashlib
from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.data_backup import create_backup, inspect_database, restore_backup
from server.database import Database, add_file_message, add_text_message, create_group, get_messages, join_group


@pytest.fixture
def populated(database, conn, users):
    room = create_group(conn, users[0], "สำรองข้อมูล CP10")
    join_group(conn, users[1], room["id"])
    add_text_message(conn, users[0], room["id"], "ข้อความก่อนสำรอง 👋")
    uploads = database.path.parent / "uploads"
    uploads.mkdir()
    content = "ไฟล์แนบจริงสำหรับกู้คืน".encode()
    stored = uploads / ("a" * 32)
    stored.write_bytes(content)
    add_file_message(conn, users[0], room["id"], stored_name=stored.name,
                     original_name="งาน.txt", size_bytes=len(content), sha256=hashlib.sha256(content).hexdigest())
    return database.path.parent, stored, room["id"], users


def test_online_wal_backup_restores_committed_messages_and_files_only(populated, conn, tmp_path):
    data, stored, room, users = populated
    (data / ".env").write_text("PRIVATE_API_KEY=not-a-real-key")
    (data / "uploads" / ".partial").mkdir()
    (data / "uploads" / ".partial" / "unfinished.part").write_bytes(b"incomplete")
    assert Path(str(data / "studygroup.db") + "-wal").stat().st_size > 0
    conn.execute("BEGIN IMMEDIATE")
    add_text_message(conn, users[0], room, "ยังไม่ commit")
    archive = tmp_path / "backups" / "cloud.zip"
    report = create_backup(data, archive)
    conn.rollback()
    assert report["counts"]["messages"] == 2
    assert archive.stat().st_mode & 0o777 == 0o600
    with ZipFile(archive) as zipped:
        assert set(zipped.namelist()) == {"manifest.json", "studygroup.db", "uploads/" + stored.name}
    add_text_message(conn, users[0], room, "เพิ่มหลังสำรอง")
    destination = tmp_path / "recovered"
    restored = restore_backup(archive, destination)
    assert restored["counts"] == report["counts"]
    assert (destination / "uploads" / stored.name).read_bytes() == stored.read_bytes()
    with Database(destination / "studygroup.db").connect() as db:
        messages = get_messages(db, users[1], room)
        assert len(messages) == 2 and messages[0]["text"] == "ข้อความก่อนสำรอง 👋"
    assert conn.execute("SELECT count(*) FROM messages").fetchone()[0] == 3


@pytest.mark.parametrize("failure", ["missing", "changed", "symlink"])
def test_bad_committed_attachment_does_not_publish_backup(populated, tmp_path, failure):
    data, stored, *_ = populated
    original = stored.read_bytes()
    stored.unlink()
    if failure == "changed":
        stored.write_bytes(b"changed")
    elif failure == "symlink":
        outside = tmp_path / "outside"
        outside.write_bytes(original)
        stored.symlink_to(outside)
    archive = tmp_path / "invalid.zip"
    with pytest.raises(ValueError):
        create_backup(data, archive)
    assert not archive.exists()


def test_backup_and_restore_refuse_to_overwrite_existing_data(populated, tmp_path):
    data, *_ = populated
    archive = tmp_path / "backup.zip"
    create_backup(data, archive)
    original = archive.read_bytes()
    with pytest.raises(FileExistsError):
        create_backup(data, archive)
    assert archive.read_bytes() == original
    with pytest.raises(FileExistsError):
        restore_backup(archive, data)
    assert inspect_database(data / "studygroup.db")[1]["messages"] == 2


@pytest.mark.parametrize("attack", ["traversal", "changed", "symlink"])
def test_restore_rejects_unsafe_or_corrupt_archive_before_creating_destination(populated, tmp_path, attack):
    data, stored, *_ = populated
    archive = tmp_path / "backup.zip"
    create_backup(data, archive)
    malicious = tmp_path / "bad.zip"
    with ZipFile(archive) as source, ZipFile(malicious, "w") as target:
        for entry in source.infolist():
            value = source.read(entry.filename)
            if entry.filename == "uploads/" + stored.name:
                if attack == "changed":
                    value = b"x" * len(value)
                elif attack == "symlink":
                    entry.create_system = 3
                    entry.external_attr = 0o120777 << 16
            target.writestr(entry, value)
        if attack == "traversal":
            target.writestr("../escape", b"outside")
    destination = tmp_path / "restored"
    with pytest.raises(ValueError):
        restore_backup(malicious, destination)
    assert not destination.exists() and not (tmp_path / "escape").exists()
