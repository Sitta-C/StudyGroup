"""Verified TCP/TLS transport used only by backend integration tests."""

from dataclasses import dataclass
from pathlib import Path
import socket
import ssl

from shared.protocol import PacketConnection


@dataclass(frozen=True)
class TLSConfig:
    host: str
    port: int
    tls_ca: Path | None


class TLSConnection(PacketConnection):
    def close(self):
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.socket.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def connect(config: TLSConfig, *, timeout=10.0) -> TLSConnection:
    """Connect only after verifying both the CA chain and the hostname."""
    context = ssl.create_default_context(cafile=str(config.tls_ca) if config.tls_ca else None)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    raw = socket.create_connection((config.host, config.port), timeout=timeout)
    try:
        secure = context.wrap_socket(raw, server_hostname=config.host)
    except BaseException:
        raw.close()
        raise
    return TLSConnection(secure)
