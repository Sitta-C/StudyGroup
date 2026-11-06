"""Isolated browser-test server. Never used as the production entry point."""
import os
from pathlib import Path
import signal
import sys
from tempfile import TemporaryDirectory
import threading
from dataclasses import replace
from http import HTTPStatus

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from server.web import WebServer, response
from server.web_config import WebConfig
from server.rate_limit import AuthRateLimiter


class FixtureServer(WebServer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.drop_next_send = threading.Event()
        original = self.router
        owner = self

        class ControlledRouter:
            def dispatch(self, connection, db, packet):
                original.dispatch(connection, db, packet)
                if packet["type"] == "MESSAGE_SEND" and owner.drop_next_send.is_set():
                    owner.drop_next_send.clear()
                    # Commit completed, but outbox response/echo hasn't been sent.
                    connection.websocket.close(1012, "Test dropped acknowledgement")

        self.router = ControlledRouter()

    def http_request(self, connection, request):
        if request.path.startswith("/__test__/"):
            # A test-only control closes real sockets; app traffic isn't mocked.
            token = os.environ.get("STUDYGROUP_TEST_CONTROL")
            if not token or request.headers.get("X-Test-Control") != token:
                return response(HTTPStatus.NOT_FOUND, "Not found")
            if request.path == "/__test__/drop-next-send":
                self.drop_next_send.set()
                return response(HTTPStatus.OK, "Armed")
            if request.path == "/__test__/message-count":
                with self.database.connect() as db:
                    count = db.execute("SELECT count(*) FROM messages").fetchone()[0]
                return response(HTTPStatus.OK, str(count))
            if request.path != "/__test__/disconnect":
                return response(HTTPStatus.NOT_FOUND, "Not found")
            with self._lock:
                connections = list(self._connections)
            for client in connections:
                client.websocket.close(1012, "Test connection interruption")
            return response(HTTPStatus.OK, "Disconnected")
        return super().http_request(connection, request)


stop = threading.Event()
signal.signal(signal.SIGTERM, lambda *_: stop.set())
signal.signal(signal.SIGINT, lambda *_: stop.set())
with TemporaryDirectory(prefix="studygroup-browser-tests-") as temporary:
    config = replace(WebConfig.from_env(), data_dir=Path(temporary))
    with FixtureServer(config, limiter=AuthRateLimiter(address_limit=1000, account_limit=50)):
        print("Isolated browser test server ready", flush=True)
        stop.wait()
