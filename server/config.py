"""Server settings, including optional AI credentials held only on the server."""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from shared.config import PROJECT_ROOT, read_data_dir, read_file, read_host, read_port


@dataclass(frozen=True)
class ServerConfig:
    host: str
    port: int
    data_dir: Path
    tls_cert: Path
    tls_key: Path
    ai_provider: str | None = None
    ai_model: str | None = None
    ai_api_key: str | None = field(default=None, repr=False)

    @property
    def database_path(self) -> Path:
        return self.data_dir / "studygroup.db"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @classmethod
    def from_env(
        cls, env: Mapping[str, str] | None = None, *, base_dir: Path = PROJECT_ROOT
    ) -> "ServerConfig":
        """Read settings without starting services or creating runtime data.

        TLS files must already exist and be readable. AI settings are optional
        until an adapter is configured in CP09. Relative paths use base_dir.
        """
        source = os.environ if env is None else env
        return cls(
            host=read_host(source),
            port=read_port(source),
            data_dir=read_data_dir(source.get("STUDYGROUP_DATA_DIR", "data"), base_dir),
            tls_cert=read_file(
                source.get("STUDYGROUP_TLS_CERT", "certs/server.crt"),
                "STUDYGROUP_TLS_CERT",
                base_dir,
            ),
            tls_key=read_file(
                source.get("STUDYGROUP_TLS_KEY", "certs/server.key"),
                "STUDYGROUP_TLS_KEY",
                base_dir,
            ),
            ai_provider=source.get("STUDYGROUP_AI_PROVIDER", "").strip() or None,
            ai_model=source.get("STUDYGROUP_AI_MODEL", "").strip() or None,
            ai_api_key=source.get("STUDYGROUP_AI_API_KEY", "").strip() or None,
        )
