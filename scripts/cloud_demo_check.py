"""Explicit CP10 demo fixtures: prepare once, verify after restart or restore.

--prepare creates three clearly named test accounts, a group, a private room,
messages and a 64 KiB file. The state file contains test passwords: keep it out
of Git. Verification accesses only these fixtures and never calls a paid AI API.
"""

import argparse
from contextlib import ExitStack
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
from urllib.parse import urlsplit

from websockets.sync.client import connect


class Peer:
    def __init__(self, stack, origin):
        scheme = "wss" if origin.startswith("https:") else "ws"
        self.ws = stack.enter_context(connect(scheme + "://" + urlsplit(origin).netloc + "/ws",
                                             origin=origin, open_timeout=15, close_timeout=2))

    def request(self, kind, data=None):
        identity = secrets.token_hex(16)
        self.ws.send(json.dumps({"v": 1, "id": identity, "type": kind, "data": data or {}}, ensure_ascii=False))
        while True:
            packet = json.loads(self.ws.recv(timeout=30))
            if packet.get("id") == identity:
                return packet["data"]

    def ok(self, kind, data=None):
        response = self.request(kind, data)
        if not response["ok"]:
            raise RuntimeError(kind + ": " + response["error"]["code"])
        return response["result"]

    def forbidden(self, kind, data):
        response = self.request(kind, data)
        if response.get("ok") or response["error"]["code"] != "FORBIDDEN":
            raise RuntimeError("Expected FORBIDDEN: " + kind)


def content(state):
    return hashlib.shake_256(state["run_id"].encode()).digest(65536)


def save_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("w", encoding="utf-8") as stream:
        json.dump(state, stream, ensure_ascii=False, indent=2)
    os.chmod(path, 0o600)


def prepare(origin, path):
    if path.exists():
        raise FileExistsError("Fixture state already exists; use --verify")
    run_id = datetime.now(timezone.utc).strftime("%m%d%H%M") + secrets.token_hex(2)
    state = {"url": origin, "run_id": run_id,
             "accounts": [{"username": f"cp10{label}_{run_id}", "password": secrets.token_urlsafe(24)} for label in "abc"]}
    save_state(path, state)
    with ExitStack() as stack:
        peers = [Peer(stack, origin) for _ in range(3)]
        for peer, account in zip(peers, state["accounts"]):
            peer.ok("REGISTER", {**account, "confirm_password": account["password"]})
            account["id"] = peer.ok("LOGIN", account)["user"]["id"]
        alice, bob, carol = peers
        state["group_id"] = alice.ok("GROUP_CREATE", {"name": "CP10 demo verification " + run_id})["room"]["id"]
        bob.ok("GROUP_JOIN", {"room_id": state["group_id"]})
        state["group_text"] = "CP10 ทดสอบข้อมูลถาวร ไทย 👋 " + run_id
        state["group_message_id"] = alice.ok("MESSAGE_SEND", {"room_id": state["group_id"], "text": state["group_text"]})["message"]["message_id"]
        state["private_id"] = alice.ok("PRIVATE_ROOM_OPEN", {"peer_id": state["accounts"][1]["id"]})["room"]["id"]
        state["private_text"] = "CP10 private " + run_id
        alice.ok("MESSAGE_SEND", {"room_id": state["private_id"], "text": state["private_text"]})
        payload = content(state)
        state["file_sha256"] = hashlib.sha256(payload).hexdigest()
        transfer = alice.ok("FILE_BEGIN", {"room_id": state["group_id"], "name": "cp10-" + run_id + ".bin",
                                          "size": len(payload), "sha256": state["file_sha256"]})
        chunk_size = transfer["chunk_size"]
        for index in range(transfer["chunks"]):
            alice.ok("FILE_CHUNK", {"transfer_id": transfer["transfer_id"], "index": index,
                                   "data": base64.b64encode(payload[index * chunk_size:(index + 1) * chunk_size]).decode()})
        state["attachment_id"] = alice.ok("FILE_END", {"transfer_id": transfer["transfer_id"]})["message"]["attachment"]["id"]
        save_state(path, state)
        for peer in peers:
            peer.ok("LOGOUT")
    return verify(origin, path)


def verify(origin, path):
    state = json.loads(path.read_text())
    with ExitStack() as stack:
        peers = [Peer(stack, origin) for _ in range(3)]
        for peer, account in zip(peers, state["accounts"]):
            peer.ok("LOGIN", {"username": account["username"], "password": account["password"]})
        alice, bob, carol = peers
        own_ids = {account["id"] for account in state["accounts"]}
        assert own_ids.issubset({user["id"] for user in alice.ok("USERS_LIST")["users"]})
        group = bob.ok("HISTORY_GET", {"room_id": state["group_id"]})["messages"]
        assert any(message.get("text") == state["group_text"] for message in group)
        private = bob.ok("HISTORY_GET", {"room_id": state["private_id"]})["messages"]
        assert any(message.get("text") == state["private_text"] for message in private)
        search = bob.ok("HISTORY_SEARCH", {"room_id": state["group_id"], "query": state["run_id"]})["messages"]
        assert any(message["message_id"] == state["group_message_id"] for message in search)
        received = bytearray()
        while True:
            part = bob.ok("FILE_GET", {"attachment_id": state["attachment_id"], "offset": len(received)})
            assert part["offset"] == len(received)
            received.extend(base64.b64decode(part["data"], validate=True))
            if part["done"]:
                break
        assert bytes(received) == content(state)
        assert hashlib.sha256(received).hexdigest() == state["file_sha256"]
        carol.forbidden("HISTORY_GET", {"room_id": state["group_id"]})
        carol.forbidden("HISTORY_GET", {"room_id": state["private_id"]})
        carol.forbidden("FILE_GET", {"attachment_id": state["attachment_id"]})
        for peer in peers:
            peer.ok("LOGOUT")
    return {"run_id": state["run_id"], "url": origin, "accounts": 3,
            "checks": ["login", "online", "group_history", "private_history", "search", "file_sha256", "outsider_forbidden"],
            "group_id": state["group_id"], "private_id": state["private_id"], "attachment_id": state["attachment_id"],
            "file_bytes": 65536, "file_sha256": state["file_sha256"], "result": "PASS"}


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Explicit HTTPS origin; localhost HTTP allowed for restore checks")
    parser.add_argument("--state", required=True, type=Path, help="Private test credentials outside Git")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    origin = args.url.rstrip("/")
    parsed = urlsplit(origin)
    if parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password or not parsed.hostname:
        parser.error("Expected an origin without a path or credentials")
    if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1")):
        parser.error("Public checks require HTTPS")
    result = prepare(origin, args.state) if args.prepare else verify(origin, args.state)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
