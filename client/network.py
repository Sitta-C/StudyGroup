"""Verified TLS transport. UI receive worker / pending requests follow in CP06."""

import socket
import ssl

from client.config import ClientConfig
from shared.protocol import PacketConnection


class TLSConnection(PacketConnection):
    def close(self):
        # Drop transport; never persist credentials or retry requests implicitly.
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.socket.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def connect(config: ClientConfig, *, timeout=10.0) -> TLSConnection:
    """Return only after CA chain AND config.host hostname checks succeed.

    There is deliberately no option to disable certificate verification.
    Credentials can be sent only through the successfully returned transport.
    """
    context = ssl.create_default_context(cafile=str(config.tls_ca) if config.tls_ca else None)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    raw = socket.create_connection((config.host, config.port), timeout=timeout)
    try:
        secure = context.wrap_socket(raw, server_hostname=config.host)
    except BaseException:
        raw.close()
        raise
    return TLSConnection(secure)
