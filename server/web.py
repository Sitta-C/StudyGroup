"""React assets + WebSocket commands on one Python server: python -m server.web."""

import io
import logging
import mimetypes
import queue
import ssl
import threading
import time
from http import HTTPStatus
from urllib.parse import unquote, urlsplit

from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Response
from websockets.sync.server import serve

from server.database import Database
from server.handlers.auth import AuthHandlers
from server.handlers.chat import ChatHandlers
from server.handlers.files import FileHandlers
from server.handlers.history import HistoryHandlers
from server.main import ServerLimits
from server.passwords import Passwords
from server.rate_limit import AuthRateLimiter
from server.router import Router
from server.sessions import SessionRegistry
from server.web_config import WebConfig
from shared.protocol import HEADER, MAX_FRAME_BYTES, encode_packet, recv_packet
from shared.validation import ProtocolError


class _MessageReader(io.BytesIO):
    recv = io.BytesIO.read


def decode_message(message):
    """WebSocket boundaries replace the TCP header; share the strict JSON codec."""
    if not isinstance(message, str):
        raise ProtocolError("INVALID_PACKET", "Expected a JSON text message")
    try:
        body = message.encode("utf-8")
    except UnicodeError:
        raise ProtocolError("INVALID_JSON", "Invalid UTF-8") from None
    if not 0 < len(body) <= MAX_FRAME_BYTES:
        raise ProtocolError("FRAME_TOO_LARGE", "Message exceeds the frame limit")
    return recv_packet(_MessageReader(HEADER.pack(len(body)) + body))


def encode_message(packet):
    return encode_packet(packet)[HEADER.size:].decode("utf-8")


def response(status, body, content_type="text/plain; charset=utf-8", *, cache="no-store"):
    if isinstance(body, str):
        body = body.encode("utf-8")
    return Response(status.value, status.phrase, Headers([
        ("Content-Type", content_type), ("Content-Length", str(len(body))),
        # The WebSocket server closes plain HTTP connections after one response;
        # say so, or keep-alive clients may reuse a closed socket (ECONNRESET).
        ("Connection", "close"),
        ("Cache-Control", cache), ("X-Content-Type-Options", "nosniff"),
        ("Referrer-Policy", "same-origin"),
        ("Content-Security-Policy", "default-src 'self'; connect-src 'self'; img-src 'self' data:; font-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'"),
    ]), body)


class WebConnection:
    """A handler thread owns command dispatch and outbound application messages."""

    def __init__(self, server, websocket):
        self.server, self.websocket = server, websocket
        self.user = None
        self.address = websocket.remote_address[0]
        self._outbox = queue.Queue(maxsize=server.limits.outbox_size)
        self._stopping = threading.Event()

    def request_close(self):
        # Called under registry locks: no network I/O or blocking waits here.
        self._stopping.set()

    def enqueue(self, packet):
        if self._stopping.is_set():
            return False
        try:
            self._outbox.put_nowait(packet)
            return True
        except queue.Full:
            self.request_close()
            return False

    def run(self):
        last_received = time.monotonic()
        try:
            with self.server.database.connect() as db:
                while not self._stopping.is_set():
                    for _ in range(64):
                        if self._stopping.is_set():
                            break
                        try:
                            packet = self._outbox.get_nowait()
                        except queue.Empty:
                            break
                        self.websocket.send(encode_message(packet))
                    limit = self.server.limits.idle_timeout if self.user else self.server.limits.auth_timeout
                    if time.monotonic() - last_received >= limit:
                        break
                    try:
                        message = self.websocket.recv(timeout=0.1)
                    except TimeoutError:
                        continue
                    request = decode_message(message)
                    last_received = time.monotonic()
                    self.server.router.dispatch(self, db, request)
        except ProtocolError:
            self.websocket.close(1008, "Invalid application message")
        except ConnectionClosed:
            pass
        except Exception:
            # Never log request payloads, credentials, SQL values or tracebacks.
            logging.getLogger(__name__).error("WebSocket connection closed after an internal error")
        finally:
            self.request_close()
            try:
                self.server.registry.logout(self)
            finally:
                # Unfinished uploads never publish; delete their partial files.
                self.server.files.connection_closed(self)
                self.websocket.close()


class WebServer:
    def __init__(self, config, *, limits=None, limiter=None):
        self.config = config
        self.limits = limits or ServerLimits()
        self.database = Database(config.database_path)
        self.registry = SessionRegistry()
        chat = ChatHandlers(self.registry)
        self.files = FileHandlers(self.registry, config.uploads_dir, chat)
        self.router = Router(AuthHandlers(self.registry, Passwords(), limiter or AuthRateLimiter(),
                                         threading.BoundedSemaphore(self.limits.hash_workers)),
                             chat, HistoryHandlers(), self.files)
        self._slots = threading.BoundedSemaphore(self.limits.max_connections)
        self._connections = set()
        self._lock = threading.Lock()
        self.http = self.thread = None
        self.address = None

    def http_request(self, connection, request):
        path = urlsplit(request.path).path
        if path == "/ws":
            return None  # The library validates Origin, Upgrade and the handshake.
        if path == "/health":
            return response(HTTPStatus.OK, '{"status":"ok"}', "application/json")
        root = self.config.static_dir.resolve()
        try:
            decoded = unquote(path)
            if "\x00" in decoded or "\\" in decoded:
                return response(HTTPStatus.BAD_REQUEST, "Invalid path")
            target = (root / ("index.html" if decoded == "/" else decoded.lstrip("/"))).resolve()
            if not target.is_relative_to(root):
                return response(HTTPStatus.NOT_FOUND, "Not found")
            if not target.is_file():
                if decoded == "/" and not (root / "index.html").is_file():
                    return response(HTTPStatus.SERVICE_UNAVAILABLE, "Build the frontend first: npm --prefix web ci && npm --prefix web run build")
                return response(HTTPStatus.NOT_FOUND, "Not found")
            body = target.read_bytes()
        except (OSError, ValueError):
            return response(HTTPStatus.NOT_FOUND, "Not found")
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in ("application/javascript", "application/json"):
            content_type += "; charset=utf-8"
        cache = "public, max-age=31536000, immutable" if target.parent.name == "assets" else "no-cache"
        return response(HTTPStatus.OK, body, content_type, cache=cache)

    def handle(self, websocket):
        if not self._slots.acquire(blocking=False):
            websocket.close(1013, "Server is busy")
            return
        connection = WebConnection(self, websocket)
        with self._lock:
            self._connections.add(connection)
        try:
            connection.run()
        finally:
            with self._lock:
                self._connections.discard(connection)
            self._slots.release()

    def start(self):
        if self.http is not None:
            raise RuntimeError("Server already started")
        context = None
        if self.config.tls_cert:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(self.config.tls_cert, self.config.tls_key)
        self.database.initialize()
        self.files.prepare(self.database)
        self.http = serve(self.handle, self.config.host, self.config.port, ssl=context,
                          origins=self.config.origins, process_request=self.http_request,
                          compression=None, server_header=None, max_size=MAX_FRAME_BYTES,
                          max_queue=16, open_timeout=self.limits.handshake_timeout,
                          close_timeout=1, ping_interval=20, ping_timeout=20)
        self.address = self.http.socket.getsockname()
        self.thread = threading.Thread(target=self.http.serve_forever, name="studygroup-web")
        self.thread.start()
        return self

    def stop(self):
        if self.http is None:
            return
        with self._lock:
            connections = list(self._connections)
        for connection in connections:
            connection.request_close()
            connection.websocket.close(1001, "Server stopping")
        self.http.shutdown()
        self.thread.join(5)
        deadline = time.monotonic() + 3
        while self._connections and time.monotonic() < deadline:
            time.sleep(0.01)

    def __enter__(self):
        return self.start()

    def __exit__(self, *_):
        self.stop()


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    # websockets' DEBUG logs may contain application payloads. Keep library
    # logging at WARNING even when app-level diagnostics are enabled.
    logging.getLogger("websockets").setLevel(logging.WARNING)
    config = WebConfig.from_env()
    with WebServer(config) as server:
        scheme = "https" if config.tls_cert else "http"
        logging.info("StudyGroup Web server: %s://%s:%s", scheme, *server.address[:2])
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
