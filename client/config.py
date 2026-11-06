"""Client connection settings; no server secrets or storage are required."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from shared.config import PROJECT_ROOT, read_file, read_host, read_port


@dataclass(frozen=True)
class ClientConfig:
    host: str
    port: int
    tls_ca: Path | None

    @classmethod
    def from_env(
        cls, env: Mapping[str, str] | None = None, *, base_dir: Path = PROJECT_ROOT
    ) -> "ClientConfig":
        """Read current environment, or an explicit mapping (including {}).

        An unset CA uses the local development CA. An explicitly empty CA
        selects the system trust store; TLS hostname checks remain required.
        Relative paths are resolved against the project root or base_dir.
        """
        source = os.environ if env is None else env
        host = read_host(source)
        port = read_port(source)
        raw_ca = source.get("STUDYGROUP_TLS_CA", "certs/ca.crt")
        tls_ca = (
            read_file(raw_ca, "STUDYGROUP_TLS_CA", base_dir) if raw_ca.strip() else None
        )
        return cls(host=host, port=port, tls_ca=tls_ca)
