"""TLS listener and service lifecycle. Run with python -m server.main."""

import logging
import math
import socket
import ssl
import threading
from dataclasses import dataclass

from server.config import ServerConfig
from server.connection import ClientConnection
from server.database import Database
from server.handlers.auth import AuthHandlers
from server.passwords import Passwords
from server.rate_limit import AuthRateLimiter
from server.router import Router
from server.sessions import SessionRegistry


@dataclass(frozen=True)
class ServerLimits:
    handshake_timeout: float = 5.0
    io_timeout: float = 5.0
    auth_timeout: float = 30.0
    idle_timeout: float = 1800.0
    max_connections: int = 128
    outbox_size: int = 128
    hash_workers: int = 2

    def __post_init__(self):
        for value in (self.handshake_timeout, self.io_timeout, self.auth_timeout, self.idle_timeout):
            if not math.isfinite(value) or value <= 0:
                raise ValueError("Timeouts must be finite and positive")
        for value in (self.max_connections, self.outbox_size, self.hash_workers):
            if type(value) is not int or value < 1:
                raise ValueError("Capacity limits must be positive integers")


class TLSServer:
    def __init__(self, config: ServerConfig, *, limits=None, limiter=None):
        self.config = config
        self.limits = limits or ServerLimits()
        self.database = Database(config.database_path)
        self.registry = SessionRegistry()
        self.limiter = limiter or AuthRateLimiter()
        self._lock = threading.Lock()
        self._connections = set()
        self._stopping = threading.Event()
        self._listener = None
        self._accept_thread = None
        self.address = None

    def start(self):
        """Bind synchronously, then accept in background. An instance starts once."""
        if self._listener is not None or self._stopping.is_set():
            raise RuntimeError("Server instance has already been started or stopped")
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.context.minimum_version = ssl.TLSVersion.TLSv1_2
        self.context.load_cert_chain(self.config.tls_cert, self.config.tls_key)
        self.database.initialize()
        self.router = Router(AuthHandlers(
            self.registry, Passwords(), self.limiter,
            threading.BoundedSemaphore(self.limits.hash_workers),
        ))
        family, socktype, proto, _, address = socket.getaddrinfo(
            self.config.host, self.config.port, type=socket.SOCK_STREAM,
        )[0]
        listener = socket.socket(family, socktype, proto)
        try:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(address)
            listener.listen(self.limits.max_connections)
            listener.settimeout(0.2)
            self.address = listener.getsockname()
            self._listener = listener
            self._accept_thread = threading.Thread(target=self._accept, name="studygroup-listener")
            self._accept_thread.start()
        except BaseException:
            listener.close()
            raise
        return self

    def _accept(self):
        while not self._stopping.is_set():
            try:
                raw, address = self._listener.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            with self._lock:
                if self._stopping.is_set() or len(self._connections) >= self.limits.max_connections:
                    raw.close()
                    continue
                connection = ClientConnection(raw, address, self)
                self._connections.add(connection)
                # Handshake belongs to this worker, so a stalled peer does not
                # hold up new accepts or other users.
                connection.thread.start()

    def connection_finished(self, connection):
        with self._lock:
            self._connections.discard(connection)

    def stop(self):
        self._stopping.set()
        if self._listener is not None:
            self._listener.close()
        if self._accept_thread is not None:
            self._accept_thread.join()
        with self._lock:
            connections = list(self._connections)
        for connection in connections:
            connection.request_close()
        # Handshake / partial frames / slow sends are bounded by socket timeout.
        for connection in connections:
            connection.thread.join()

    def __enter__(self):
        return self.start()

    def __exit__(self, *_):
        self.stop()


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    config = ServerConfig.from_env()
    with TLSServer(config) as server:
        logging.info("StudyGroup TLS server listening on %s:%s", *server.address[:2])
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
