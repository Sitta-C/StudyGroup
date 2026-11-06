"""Real WebSocket peers for CP07/CP08 integration tests (not a test module)."""

import base64
import hashlib
import json
import math

from websockets.sync.client import connect

from shared.message_types import RequestType as R
from shared.protocol import make_request

ORIGIN = "http://localhost:8765"
PASSWORD = "history test password🔑"
CHUNK = 32 * 1024


def connect_peer(server):
    scheme = "wss" if server.config.tls_cert else "ws"
    websocket = connect(f"{scheme}://127.0.0.1:{server.address[1]}/ws", origin=ORIGIN,
                        proxy=None, close_timeout=1, open_timeout=3, max_size=2**21)
    return Peer(websocket)


class Peer:
    def __init__(self, websocket):
        self.ws = websocket
        self.events = []
        self.user = None

    def __enter__(self):
        self.ws.__enter__()
        return self

    def __exit__(self, *exc):
        return self.ws.__exit__(*exc)

    def send(self, kind, data=None):
        request = make_request(kind, data or {})
        self.ws.send(json.dumps(request, ensure_ascii=False))
        return request["id"]

    def wait(self, request_id):
        while True:
            packet = json.loads(self.ws.recv(timeout=10))
            if packet.get("id") == request_id:
                return packet["data"]
            self.events.append(packet)

    def request(self, kind, data=None):
        return self.wait(self.send(kind, data))

    def ok(self, kind, data=None):
        response = self.request(kind, data)
        assert response["ok"], response
        return response["result"]

    def error(self, kind, data=None):
        response = self.request(kind, data)
        assert not response["ok"], response
        return response["error"]["code"]

    def register(self, username):
        self.ok(R.REGISTER, {"username": username, "password": PASSWORD, "confirm_password": PASSWORD})
        return self.login(username)

    def login(self, username):
        self.user = self.ok(R.LOGIN, {"username": username, "password": PASSWORD})["user"]
        return self.user

    def drain(self, kind):
        self.ok(R.USERS_LIST)
        result = [packet["data"] for packet in self.events if packet["type"] == kind]
        self.events = [packet for packet in self.events if packet["type"] != kind]
        return result

    def say(self, room_id, text):
        return self.ok(R.MESSAGE_SEND, {"room_id": room_id, "text": text})["message"]

    def upload(self, room_id, name, content, *, digest=None):
        begin = self.ok(R.FILE_BEGIN, {"room_id": room_id, "name": name, "size": len(content),
                                       "sha256": digest or hashlib.sha256(content).hexdigest()})
        assert begin["chunk_size"] == CHUNK and begin["chunks"] == math.ceil(len(content) / CHUNK)
        for index in range(begin["chunks"]):
            piece = content[index * CHUNK:(index + 1) * CHUNK]
            self.ok(R.FILE_CHUNK, {"transfer_id": begin["transfer_id"], "index": index,
                                   "data": base64.b64encode(piece).decode()})
        return self.request(R.FILE_END, {"transfer_id": begin["transfer_id"]})

    def download(self, attachment_id):
        content, offset = bytearray(), 0
        while True:
            chunk = self.ok(R.FILE_GET, {"attachment_id": attachment_id, "offset": offset})
            assert chunk["offset"] == offset
            data = base64.b64decode(chunk["data"], validate=True)
            content += data
            offset += len(data)
            if chunk["done"]:
                assert offset == chunk["size"]
                return bytes(content), chunk
