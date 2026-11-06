"""Environment parsing without loading .env files or changing the filesystem."""

import ipaddress
import os
import re
from collections.abc import Mapping
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ConfigError(ValueError):
    """An environment setting cannot be used by the application."""


def read_host(env: Mapping[str, str]) -> str:
    name = "STUDYGROUP_HOST"
    host = env.get(name, "127.0.0.1").strip()
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    try:
        hostname = host.encode("idna").decode("ascii").removesuffix(".")
    except UnicodeError:
        hostname = ""
    labels = hostname.split(".")
    if not hostname or len(hostname) > 253 or any(
        not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", label)
        for label in labels
    ):
        raise ConfigError(f"{name}: expected a hostname or IP address without a port or URL")
    return host


def read_port(env: Mapping[str, str]) -> int:
    name = "STUDYGROUP_PORT"
    raw = env.get(name, "5000").strip()
    # int() alone also accepts underscores and non-ASCII numerals.
    if not re.fullmatch(r"[0-9]{1,5}", raw):
        raise ConfigError(f"{name}: expected an integer between 1 and 65535")
    port = int(raw)
    if not 1 <= port <= 65535:
        raise ConfigError(f"{name}: expected an integer between 1 and 65535")
    return port


def read_path(raw: str, name: str, base_dir: Path) -> Path:
    if not raw.strip() or "\x00" in raw:
        raise ConfigError(f"{name}: expected a non-empty filesystem path without NUL characters")
    try:
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = base_dir / path
        return path.resolve()
    except (OSError, RuntimeError, ValueError):
        raise ConfigError(f"{name}: could not resolve filesystem path") from None


def read_file(raw: str, name: str, base_dir: Path) -> Path:
    path = read_path(raw, name, base_dir)
    try:
        if not path.is_file():
            raise ConfigError(f"{name}: expected an existing readable file; check the path and TLS setup")
        with path.open("rb"):
            pass
    except OSError:
        raise ConfigError(f"{name}: could not read file; check the path and permissions") from None
    return path


def read_data_dir(raw: str, base_dir: Path) -> Path:
    name = "STUDYGROUP_DATA_DIR"
    path = read_path(raw, name, base_dir)
    # New data directories are allowed. Startup, rather than config loading,
    # will create them after all settings have been validated.
    ancestor = path
    try:
        while not ancestor.exists() and ancestor != ancestor.parent:
            ancestor = ancestor.parent
        if not ancestor.is_dir():
            raise ConfigError(f"{name}: expected a directory; path or parent is a file")
        if not os.access(ancestor, os.W_OK | os.X_OK):
            raise ConfigError(f"{name}: directory or nearest existing parent must be writable and searchable")
    except OSError:
        raise ConfigError(f"{name}: could not inspect directory; check the path and permissions") from None
    return path
