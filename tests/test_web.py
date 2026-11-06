"""Browser transport over real HTTP/WebSocket/WSS and temporary SQLite."""

from dataclasses import replace
import http.client
import json
from pathlib import Path
import ssl

import pytest
from websockets.exceptions import ConnectionClosed, InvalidStatus
from websockets.sync.client import connect

from server.web import WebServer
from server.web_config import WebConfig
from shared.config import ConfigError
from shared.message_types import RequestType as R
from shared.protocol import make_request

ORIGIN = "http://localhost:8765"
PASSWORD = "web test password🔑"


@pytest.fixture
def web_factory(tmp_path):
    servers = []
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text('<!doctype html><title>StudyGroup</title>')
    (static / "assets").mkdir()
    (static / "assets" / "app.js").write_text('console.log("public asset")')

    def start(**options):
        config = WebConfig("127.0.0.1", 0, tmp_path / f"data-{len(servers)}", static, (ORIGIN,))
        config = replace(config, **options)
        server = WebServer(config).start()
        servers.append(server)
        return server

    yield start
    for server in reversed(servers):
        server.stop()
        assert server.registry.users() == []
        assert not server._connections
        assert not server.thread.is_alive()


@pytest.fixture
def web(web_factory):
    return web_factory()


def peer(server, **options):
    scheme = "wss" if server.config.tls_cert else "ws"
    return connect(f"{scheme}://127.0.0.1:{server.address[1]}/ws", origin=ORIGIN,
                   proxy=None, close_timeout=1, open_timeout=3, **options)


class BrowserPeer:
    def __init__(self, websocket):
        self.ws = websocket
        self.events = []
        self.user = None

    def request(self, kind, data=None):
        request = make_request(kind, data or {})
        self.ws.send(json.dumps(request, ensure_ascii=False))
        while True:
            packet = json.loads(self.ws.recv(timeout=5))
            if packet.get("id") == request["id"]:
                return packet["data"]
            self.events.append(packet)

    def ok(self, kind, data=None):
        response = self.request(kind, data)
        assert response["ok"], response
        return response["result"]

    def login(self, username):
        self.ok(R.REGISTER, {"username": username, "password": PASSWORD, "confirm_password": PASSWORD})
        self.user = self.ok(R.LOGIN, {"username": username, "password": PASSWORD})["user"]

    def drain(self, kind):
        self.ok(R.USERS_LIST)
        result = [packet["data"] for packet in self.events if packet["type"] == kind]
        self.events.clear()
        return result


def get(server, path):
    client = http.client.HTTPConnection("127.0.0.1", server.address[1], timeout=3)
    try:
        client.request("GET", path)
        response = client.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        client.close()


def test_web_config_needs_no_legacy_certificates_and_separates_ports(tmp_path):
    config = WebConfig.from_env({"STUDYGROUP_PORT": "5001"}, base_dir=tmp_path)
    assert config.port == 8000
    assert config.data_dir == tmp_path / "data"
    assert config.static_dir == tmp_path / "web/dist"
    assert config.tls_cert is None
    assert "http://localhost:8000" in config.origins
    assert "http://127.0.0.1:5173" in config.origins


@pytest.mark.parametrize("env", [
    {"STUDYGROUP_WEB_PORT": "bad"}, {"STUDYGROUP_WEB_HOST": "https://localhost"},
    {"STUDYGROUP_WEB_ORIGINS": "*"}, {"STUDYGROUP_WEB_ORIGINS": ""},
    {"STUDYGROUP_WEB_ORIGINS": "https://user:secret@example.com"},
    {"STUDYGROUP_WEB_ORIGINS": "https://example.com/path"},
    {"STUDYGROUP_WEB_ORIGINS": "https://example.com:99999"},
    {"STUDYGROUP_WEB_TLS_CERT": "cert.pem"},
])
def test_invalid_web_config(env, tmp_path):
    with pytest.raises(ConfigError):
        WebConfig.from_env(env, base_dir=tmp_path)


def test_http_assets_health_csp_and_traversal(web, tmp_path):
    status, headers, body = get(web, "/")
    assert status == 200 and b"StudyGroup" in body
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert headers["Cache-Control"] == "no-cache"
    status, headers, body = get(web, "/assets/app.js?v=1")
    assert status == 200 and "javascript" in headers["Content-Type"]
    assert "immutable" in headers["Cache-Control"]
    assert get(web, "/health")[2] == b'{"status":"ok"}'
    secret = tmp_path / "secret.txt"
    secret.write_text("private server data")
    (web.config.static_dir / "leak").symlink_to(secret)
    for path in ("/%2e%2e/secret.txt", "/leak", "/.env", "/assets/missing.js", "/data/studygroup.db"):
        result = get(web, path)
        assert result[0] == 404 and b"private server data" not in result[2]
    assert get(web, "/%00")[0] == 400


def test_missing_build_is_a_clear_503(web_factory, tmp_path):
    web = web_factory(static_dir=tmp_path / "not-built")
    assert get(web, "/")[0] == 503
    assert get(web, "/health")[0] == 200


@pytest.mark.parametrize("origin", [None, "https://evil.example", "null", "http://localhost:8765.evil.example"])
def test_websocket_origin_rejected_before_login(web, origin):
    with pytest.raises(InvalidStatus) as error:
        connect(f"ws://127.0.0.1:{web.address[1]}/ws", origin=origin, proxy=None, close_timeout=1)
    assert error.value.response.status_code == 403
    assert web.registry.users() == []


def test_register_login_private_groups_join_visibility_and_cleanup(web):
    with peer(web) as wa, peer(web) as wb, peer(web) as wc:
        a, b, c = (BrowserPeer(ws) for ws in (wa, wb, wc))
        assert a.request(R.USERS_LIST)["error"]["code"] == "AUTH_REQUIRED"
        for client, name in ((a, "Alice"), (b, "Bob"), (c, "Carol")):
            client.login(name)
        assert len(c.ok(R.USERS_LIST)["users"]) == 3
        private = a.ok(R.PRIVATE_ROOM_OPEN, {"peer_id": b.user["id"]})["room"]["id"]
        message = a.ok(R.MESSAGE_SEND, {"room_id": private, "text": "ไทย 👋\nบรรทัดสอง"})["message"]
        assert a.drain("MESSAGE_NEW") == [message]
        assert b.drain("MESSAGE_NEW") == [message]
        assert c.drain("MESSAGE_NEW") == []
        assert c.request(R.MESSAGE_SEND, {"room_id": private, "text": "probe"})["error"]["code"] == "FORBIDDEN"
        assert a.request(R.MESSAGE_SEND, {"room_id": private, "text": "spoof", "sender_id": c.user["id"]})["error"]["code"] == "INVALID_INPUT"
        group = a.ok(R.GROUP_CREATE, {"name": "Network Project"})["room"]
        assert [m["id"] for m in group["members"]] == [a.user["id"]]
        assert c.ok(R.GROUP_LIST)["groups"] == [group]
        a.ok(R.MESSAGE_SEND, {"room_id": group["id"], "text": "ก่อนเข้าร่วม"})
        assert b.drain("MESSAGE_NEW") == []
        b.ok(R.GROUP_JOIN, {"room_id": group["id"]})
        after = b.ok(R.MESSAGE_SEND, {"room_id": group["id"], "text": "หลังเข้าร่วม"})["message"]
        assert b.drain("MESSAGE_NEW") == [after]
        assert c.drain("MESSAGE_NEW") == []
        b.ok(R.LOGOUT)
        assert len(a.ok(R.USERS_LIST)["users"]) == 2


@pytest.mark.parametrize("payload", [
    b'{}', '{"v":1,"v":1,"type":"LOGIN","id":"x","data":{}}',
    '{"v":1,"type":"USERS_UPDATED","data":{"users":[]}}',
    '{"v":1,"type":"LOGIN","id":"x","data":{"username":"Alice","password":"\\ud800"}}',
])
def test_invalid_messages_close_connection(web, payload):
    with peer(web) as ws:
        ws.send(payload)
        with pytest.raises(ConnectionClosed) as error:
            ws.recv(timeout=3)
        assert error.value.rcvd.code == 1008


def test_wss_checks_certificate_and_hostname(web_factory, certificates):
    web = web_factory(tls_cert=certificates / "server.crt", tls_key=certificates / "server.key")
    context = ssl.create_default_context(cafile=certificates / "ca.crt")
    with peer(web, ssl=context) as ws:
        client = BrowserPeer(ws)
        client.login("SecureAlice")
        assert client.ok(R.USERS_LIST)["users"] == [client.user]
    with pytest.raises(ssl.SSLCertVerificationError):
        with peer(web):
            pass


def test_restart_preserves_accounts_rooms_and_messages(web_factory):
    first = web_factory()
    with peer(first) as ws:
        client = BrowserPeer(ws)
        client.login("Alice")
        room = client.ok(R.GROUP_CREATE, {"name": "คงอยู่หลัง restart"})["room"]
        client.ok(R.MESSAGE_SEND, {"room_id": room["id"], "text": "persisted"})
    first.stop()
    second = web_factory(data_dir=first.config.data_dir)
    with peer(second) as ws:
        client = BrowserPeer(ws)
        assert client.request(R.USERS_LIST)["error"]["code"] == "AUTH_REQUIRED"
        client.ok(R.LOGIN, {"username": "Alice", "password": PASSWORD})
        assert client.ok(R.GROUP_LIST)["groups"] == [room]
    with second.database.connect() as db:
        assert db.execute("SELECT text FROM messages").fetchone()[0] == "persisted"
