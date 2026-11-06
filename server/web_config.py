"""Browser server configuration, independent of the legacy TCP/TLS client."""

from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import urlsplit

from shared.config import ConfigError, PROJECT_ROOT, read_data_dir, read_file, read_host, read_path, read_port


@dataclass(frozen=True)
class WebConfig:
    host: str
    port: int
    data_dir: Path
    static_dir: Path
    origins: tuple[str, ...]
    tls_cert: Path | None = None
    tls_key: Path | None = None

    @property
    def database_path(self):
        return self.data_dir / "studygroup.db"

    @classmethod
    def from_env(cls, env=None, *, base_dir=PROJECT_ROOT):
        source = os.environ if env is None else env
        try:
            host = read_host({"STUDYGROUP_HOST": source.get("STUDYGROUP_WEB_HOST", "127.0.0.1")})
            port = read_port({"STUDYGROUP_PORT": source.get("STUDYGROUP_WEB_PORT", "8000")})
        except ConfigError as error:
            raise ConfigError(str(error).replace("STUDYGROUP_HOST", "STUDYGROUP_WEB_HOST").replace("STUDYGROUP_PORT", "STUDYGROUP_WEB_PORT")) from None
        cert = source.get("STUDYGROUP_WEB_TLS_CERT", "").strip()
        key = source.get("STUDYGROUP_WEB_TLS_KEY", "").strip()
        if bool(cert) != bool(key):
            raise ConfigError("STUDYGROUP_WEB_TLS_CERT and STUDYGROUP_WEB_TLS_KEY must be set together")
        scheme = "https" if cert else "http"
        defaults = f"{scheme}://localhost:{port},{scheme}://127.0.0.1:{port},http://localhost:5173,http://127.0.0.1:5173"
        origins = tuple(dict.fromkeys(value.strip().removesuffix("/") for value in source.get("STUDYGROUP_WEB_ORIGINS", defaults).split(",")))
        for origin in origins:
            try:
                parsed = urlsplit(origin)
                valid = (parsed.scheme in ("http", "https") and parsed.hostname and not parsed.username
                         and not parsed.password and not parsed.path and not parsed.query and not parsed.fragment)
                parsed.port  # Validate the optional port.
            except ValueError:
                valid = False
            if not valid or "*" in origin:
                raise ConfigError("STUDYGROUP_WEB_ORIGINS: expected explicit http(s) origins separated by commas")
        return cls(
            host, port,
            read_data_dir(source.get("STUDYGROUP_DATA_DIR", "data"), base_dir),
            read_path(source.get("STUDYGROUP_WEB_STATIC_DIR", "web/dist"), "STUDYGROUP_WEB_STATIC_DIR", base_dir),
            origins,
            read_file(cert, "STUDYGROUP_WEB_TLS_CERT", base_dir) if cert else None,
            read_file(key, "STUDYGROUP_WEB_TLS_KEY", base_dir) if key else None,
        )
