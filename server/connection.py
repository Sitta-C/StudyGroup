"""One owner thread performs all TLS I/O; other workers enqueue packets only."""

import logging
import queue
import select
import socket
import threading
import time

from shared.protocol import IncompleteFrameError, PacketConnection, recv_packet
from shared.validation import ProtocolError

logger = logging.getLogger(__name__)


class _FrameReader:
    """A total frame deadline, including peers that drip one byte at a time."""

    def __init__(self, sock, timeout):
        self.socket = sock
        self.deadline = time.monotonic() + timeout

    def recv(self, size):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Frame deadline exceeded")
        self.socket.settimeout(remaining)
        return self.socket.recv(size)


class ClientConnection:
    def __init__(self, raw, address, server):
        self.socket = raw
        self.address = address[0]
        self.server = server
        self.user = None  # mutated only by SessionRegistry
        self._outbox = queue.Queue(maxsize=server.limits.outbox_size)
        self._stopping = threading.Event()
        self._wake_read, self._wake_write = socket.socketpair()
        self._wake_read.setblocking(False)
        self._wake_write.setblocking(False)
        self.thread = threading.Thread(target=self.run, name="studygroup-client")

    def _wake(self):
        try:
            self._wake_write.send(b"x")
        except (OSError, BlockingIOError):
            pass  # A full wake pipe is already readable; closed means cleanup.

    def request_close(self):
        self._stopping.set()
        self._wake()

    def enqueue(self, packet):
        if self._stopping.is_set():
            return False
        try:
            self._outbox.put_nowait(packet)
        except queue.Full:
            self.request_close()  # Slow peers cannot block the registry lock.
            return False
        self._wake()
        return True

    def _flush(self, transport):
        # A bounded batch gives incoming requests and shutdown a chance to run.
        for _ in range(64):
            if self._stopping.is_set():
                break
            try:
                packet = self._outbox.get_nowait()
            except queue.Empty:
                break
            transport.send_packet(packet)

    def run(self):
        limits = self.server.limits
        try:
            self.socket.settimeout(limits.handshake_timeout)
            self.socket = self.server.context.wrap_socket(
                self.socket, server_side=True, do_handshake_on_connect=False,
            )
            self.socket.do_handshake()
            self.socket.settimeout(limits.io_timeout)
            transport = PacketConnection(self.socket)
            last_received = time.monotonic()
            # Each worker creates and closes its own SQLite connection.
            with self.server.database.connect() as db:
                while not self._stopping.is_set():
                    self._flush(transport)
                    idle = limits.idle_timeout if self.user else limits.auth_timeout
                    remaining = idle - (time.monotonic() - last_received)
                    if remaining <= 0:
                        break
                    readable, _, _ = select.select(
                        [self.socket, self._wake_read], [], [],
                        0 if self.socket.pending() or not self._outbox.empty() else min(remaining, 1.0),
                    )
                    if self._wake_read in readable:
                        try:
                            while self._wake_read.recv(4096):
                                pass
                        except BlockingIOError:
                            pass
                    if self.socket in readable or self.socket.pending():
                        try:
                            request = recv_packet(_FrameReader(self.socket, limits.io_timeout))
                        finally:
                            self.socket.settimeout(limits.io_timeout)
                        if request is None:
                            break
                        last_received = time.monotonic()
                        self.server.router.dispatch(self, db, request)
        except (OSError, IncompleteFrameError, ProtocolError):
            # Expected peer failure; never log received payload or credentials.
            pass
        except Exception:
            # Exception text/tracebacks may contain SQL values or credentials.
            logger.error("Connection worker failed; connection closed")
        finally:
            self._stopping.set()
            try:
                self.server.registry.logout(self)
            finally:
                self.socket.close()
                self._wake_read.close()
                self._wake_write.close()
                self.server.connection_finished(self)
