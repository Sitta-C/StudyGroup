"""Verified TLS transport and a single I/O owner for the desktop client."""

import io
import queue
import select
import socket
import ssl
import threading
import time

from client.config import ClientConfig
from shared.message_types import EventType, RESPONSE_TYPE
from shared.protocol import HEADER, MAX_FRAME_BYTES, PacketConnection, encode_packet, make_request, recv_packet
from shared.validation import ProtocolError


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


class NetworkWorker:
    """All TLS operations happen in this thread, never in a Tk callback.

    Public methods only enqueue/wake. Consumers drain ``events`` on their own
    thread. No replay, reconnect, credentials on disk, or hidden request retries.
    Closing is asynchronous; even a stalled handshake cannot freeze the UI.
    """

    def __init__(self, config, *, io_timeout=5.0, request_timeout=15.0, queue_size=256):
        self.config = config
        self.io_timeout = io_timeout
        self.request_timeout = request_timeout
        self.events = queue.Queue(maxsize=queue_size)
        self._outbox = queue.Queue(maxsize=queue_size)
        self._stopping = threading.Event()
        self._wake_read, self._wake_write = socket.socketpair()
        self._wake_read.setblocking(False)
        self._wake_write.setblocking(False)
        self.thread = threading.Thread(target=self._run, name="studygroup-network", daemon=True)

    def start(self):
        self.thread.start()
        return self

    def _wake(self):
        try:
            self._wake_write.send(b"x")
        except OSError:
            pass

    def submit(self, kind, data):
        if self._stopping.is_set():
            raise ConnectionError("Connection is closed")
        packet = make_request(kind, data)
        try:
            self._outbox.put_nowait((encode_packet(packet), packet["id"], time.monotonic() + self.request_timeout))
        except queue.Full:
            raise ConnectionError("Request queue is full") from None
        self._wake()
        return packet["id"]

    def close(self):
        self._stopping.set()
        self._wake()

    def _emit(self, event):
        try:
            self.events.put_nowait(event)
        except queue.Full:
            raise ConnectionError("UI queue is full") from None

    def _run(self):
        transport = None
        pending = {}
        reason = "STOPPED"
        try:
            transport = connect(self.config, timeout=self.io_timeout)
            if self._stopping.is_set():
                return
            # select() can report TLS control records as readable even when no
            # application bytes exist (notably TLS 1.3 session tickets). Keep
            # TLS nonblocking so those records cannot starve outbound requests.
            transport.socket.setblocking(False)
            self._emit({"type": "connected"})
            incoming = bytearray()
            frame_started = None
            outgoing = None
            send_wants_read = receive_wants_write = False
            while not self._stopping.is_set():
                now = time.monotonic()
                if pending and min(pending.values()) <= now:
                    raise TimeoutError
                if frame_started is not None and now - frame_started >= self.io_timeout:
                    raise TimeoutError
                if outgoing is None:
                    try:
                        frame, request_id, deadline = self._outbox.get_nowait()
                    except queue.Empty:
                        pass
                    else:
                        if now >= deadline or len(pending) >= 256:
                            raise TimeoutError
                        pending[request_id] = deadline
                        outgoing = memoryview(frame)
                        del frame
                if outgoing is not None:
                    try:
                        sent = transport.socket.send(outgoing)
                        if sent == 0:
                            raise ConnectionError("TLS stream closed")
                        outgoing = outgoing[sent:] if sent < len(outgoing) else None
                        send_wants_read = False
                    except ssl.SSLWantReadError:
                        send_wants_read = True
                    except ssl.SSLWantWriteError:
                        send_wants_read = False
                deadlines = [now + 0.2, *pending.values()]
                if frame_started is not None:
                    deadlines.append(frame_started + self.io_timeout)
                readable, writable, _ = select.select(
                    [transport.socket, self._wake_read],
                    [transport.socket] if (outgoing is not None and not send_wants_read) or receive_wants_write else [], [],
                    0 if transport.socket.pending() or (outgoing is None and not self._outbox.empty()) else max(0, min(deadlines) - time.monotonic()),
                )
                if self._wake_read in readable:
                    try:
                        while self._wake_read.recv(4096):
                            pass
                    except BlockingIOError:
                        pass
                if transport.socket in readable or transport.socket.pending() or (receive_wants_write and writable):
                    for _ in range(32):
                        try:
                            chunk = transport.socket.recv(65536)
                        except ssl.SSLWantReadError:
                            receive_wants_write = False
                            break
                        except ssl.SSLWantWriteError:
                            receive_wants_write = True
                            break
                        if not chunk:
                            if incoming:
                                raise EOFError
                            reason = "EOF"
                            self._stopping.set()
                            break
                        if not incoming:
                            frame_started = time.monotonic()
                        incoming.extend(chunk)
                        while len(incoming) >= HEADER.size:
                            size = HEADER.unpack(incoming[:HEADER.size])[0]
                            if not 0 < size <= MAX_FRAME_BYTES:
                                raise ProtocolError("INVALID_FRAME", "Frame size is invalid")
                            end = HEADER.size + size
                            if len(incoming) < end:
                                break
                            # Use the shared decoder after a whole frame exists;
                            # it never performs a blocking TLS read here.
                            reader = io.BytesIO(incoming[:end])
                            reader.recv = reader.read
                            packet = recv_packet(reader)
                            del incoming[:end]
                            frame_started = time.monotonic() if incoming else None
                            if packet["type"] == RESPONSE_TYPE:
                                if packet["id"] not in pending:
                                    raise ProtocolError("INVALID_PACKET", "Unexpected response")
                                pending.pop(packet["id"])
                            elif packet["type"] not in EventType:
                                raise ProtocolError("INVALID_PACKET", "Unexpected request")
                            self._emit({"type": "packet", "packet": packet})
        except ssl.SSLCertVerificationError:
            reason = "TLS"
        except TimeoutError:
            reason = "TIMEOUT"
        except (ProtocolError, EOFError):
            reason = "PROTOCOL"
        except (OSError, ValueError):
            reason = "CONNECTION"
        finally:
            self._stopping.set()
            if transport is not None:
                transport.close()
            self._wake_read.close()
            self._wake_write.close()
            while not self._outbox.empty():
                self._outbox.get_nowait()
            # Reserve a terminal notification even when a stalled UI filled the
            # queue. Dropping a response leaves its outcome uncertain, not sent.
            terminal = {"type": "disconnected", "reason": reason}
            try:
                self.events.put_nowait(terminal)
            except queue.Full:
                try:
                    self.events.get_nowait()
                except queue.Empty:
                    pass
                self.events.put_nowait(terminal)
