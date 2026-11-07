"""Back up SQLite plus committed attachments; restore only into a new directory.

Uses SQLite's online backup API, not a copy of the live .db/WAL files. Published
attachments are immutable in StudyGroup; copy only files referenced by that
database snapshot, and reject a missing or changed file. Never overwrites live
data. No API keys, partial uploads, or unrelated files are included.
"""

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import tempfile
from datetime import datetime, timezone
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile


DATABASE = "studygroup.db"
TABLES = ("users", "rooms", "room_members", "messages", "attachments")
STORED_NAME = re.compile(r"[0-9a-f]{32}\Z")
MAX_RESTORE_BYTES = 1024 * 1024 * 1024


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inspect_database(path):
    """Return attachment inventory and counts without returning private rows."""
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Database integrity check failed")
        if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ValueError("Database foreign key check failed")
        rows = db.execute(
            "SELECT stored_name, size_bytes, sha256 FROM attachments "
            "WHERE status = 'ready' ORDER BY stored_name"
        ).fetchall()
        files = []
        for name, size, sha256 in rows:
            if not STORED_NAME.fullmatch(name) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
                raise ValueError("Invalid attachment metadata")
            files.append({"name": "uploads/" + name, "size": size, "sha256": sha256})
        counts = {table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in TABLES}
    return files, counts


def create_backup(data_dir, output):
    data_dir, output = Path(data_dir).resolve(), Path(output).absolute()
    source = data_dir / DATABASE
    if not source.is_file() or source.is_symlink():
        raise ValueError("Expected an existing regular studygroup.db")
    if (data_dir / "uploads").is_symlink():
        raise ValueError("Uploads must not be a symlink")
    if output.exists() or output.is_symlink():
        raise FileExistsError("Backup destination already exists")
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix=".studygroup-backup-", dir=output.parent) as work:
        work = Path(work)
        snapshot = work / DATABASE
        source_db = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=10)
        target_db = sqlite3.connect(snapshot)
        try:
            source_db.backup(target_db, pages=256, sleep=0.05)
            target_db.execute("PRAGMA journal_mode=DELETE")
        finally:
            target_db.close()
            source_db.close()
        files, counts = inspect_database(snapshot)
        (work / "uploads").mkdir()
        for item in files:
            original = data_dir / item["name"]
            if original.is_symlink() or not original.is_file() or original.resolve().parent != (data_dir / "uploads").resolve():
                raise ValueError("Missing or unsafe committed attachment")
            copied = work / item["name"]
            shutil.copyfile(original, copied)
            if copied.stat().st_size != item["size"] or digest(copied) != item["sha256"]:
                raise ValueError("Attachment size or SHA-256 does not match database")
        manifest = {
            "format": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "database": {"name": DATABASE, "size": snapshot.stat().st_size, "sha256": digest(snapshot)},
            "files": files,
        }
        archive = work / "backup.zip"
        with ZipFile(archive, "w", compression=ZIP_DEFLATED) as zipped:
            zipped.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
            zipped.write(snapshot, DATABASE)
            for item in files:
                zipped.write(work / item["name"], item["name"])
        os.chmod(archive, 0o600)
        # Atomic publication, including a race-safe refusal to replace an archive.
        os.link(archive, output)
    return {"archive": str(output), "sha256": digest(output), "counts": counts, "files": len(files)}


def restore_backup(archive, destination):
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("Restore requires a new directory; live data is never overwritten")
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix=".studygroup-restore-", dir=destination.parent) as work:
        work = Path(work)
        with ZipFile(archive) as zipped:
            members = zipped.infolist()
            names = [item.filename for item in members]
            if len(names) != len(set(names)):
                raise ValueError("Duplicate archive member")
            if sum(item.file_size for item in members) > MAX_RESTORE_BYTES:
                raise ValueError("Archive exceeds restore size limit")
            if "manifest.json" not in names or zipped.getinfo("manifest.json").file_size > 8 * 1024 * 1024:
                raise ValueError("Missing or oversized backup manifest")
            manifest = json.loads(zipped.read("manifest.json"))
            if manifest.get("format") != 1 or manifest["database"]["name"] != DATABASE:
                raise ValueError("Unsupported backup format")
            inventory = [manifest["database"], *manifest["files"]]
            expected = {"manifest.json", DATABASE}
            for item in manifest["files"]:
                if not re.fullmatch(r"uploads/[0-9a-f]{32}", item["name"]):
                    raise ValueError("Unsafe archive path")
                expected.add(item["name"])
            if set(names) != expected or len(inventory) != len(expected) - 1:
                raise ValueError("Archive contents do not match manifest")
            for member in members:
                if member.is_dir() or stat.S_ISLNK(member.external_attr >> 16):
                    raise ValueError("Directories and symlinks are not allowed in backup archives")
            (work / "uploads").mkdir()
            for item in inventory:
                if zipped.getinfo(item["name"]).file_size != item["size"]:
                    raise ValueError("Archive member size does not match manifest")
                target = work / item["name"]
                with zipped.open(item["name"]) as source, target.open("xb") as sink:
                    shutil.copyfileobj(source, sink)
                os.chmod(target, 0o600)
                if digest(target) != item["sha256"]:
                    raise ValueError("Archive member SHA-256 does not match manifest")
        files, counts = inspect_database(work / DATABASE)
        if files != manifest["files"]:
            raise ValueError("Restored attachment inventory does not match database")
        # Reserve a new destination only after every byte has been verified.
        destination.mkdir(mode=0o700)
        try:
            (work / DATABASE).rename(destination / DATABASE)
            (work / "uploads").rename(destination / "uploads")
        except BaseException:
            shutil.rmtree(destination)
            raise
    return {"restored_to": str(destination), "counts": counts, "files": len(files)}


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    backup = commands.add_parser("backup")
    backup.add_argument("--data-dir", required=True, type=Path)
    backup.add_argument("--output", required=True, type=Path)
    restore = commands.add_parser("restore")
    restore.add_argument("--archive", required=True, type=Path)
    restore.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = (create_backup(args.data_dir, args.output) if args.command == "backup"
                  else restore_backup(args.archive, args.destination))
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error, BadZipFile) as error:
        parser.exit(1, f"Backup/restore failed: {error}\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
