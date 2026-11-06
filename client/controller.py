"""Main-thread request dispatch and chat state, independent of Tk widgets."""

import queue

from client.network import NetworkWorker
from client.session import Session
from shared.message_types import EventType, RequestType as R, RESPONSE_TYPE


ERRORS = {
    "AUTH_FAILED": "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง",
    "USERNAME_TAKEN": "ชื่อผู้ใช้นี้ถูกใช้แล้ว กรุณาเลือกชื่อใหม่",
    "ALREADY_LOGGED_IN": "บัญชีนี้เข้าสู่ระบบอยู่แล้ว กรุณาออกจากระบบที่เครื่องเดิมก่อน",
    "RATE_LIMITED": "ลองบ่อยเกินไป กรุณารอสักครู่แล้วลองใหม่",
    "FORBIDDEN": "คุณยังไม่มีสิทธิ์ใช้งานห้องนี้",
    "AUTH_REQUIRED": "กรุณาเข้าสู่ระบบอีกครั้ง",
    "INVALID_INPUT": "ข้อมูลไม่ถูกต้อง กรุณาตรวจชื่อ รหัสผ่าน หรือความยาวข้อความ",
    "FRAME_TOO_LARGE": "ข้อมูลมีขนาดใหญ่เกินไป กรุณาลองโหลดใหม่",
    "INTERNAL_ERROR": "Server ทำรายการไม่สำเร็จ กรุณาลองใหม่",
}
DISCONNECTS = {
    "TLS": "ตรวจสอบใบรับรองไม่ได้ กรุณาตรวจชื่อ Server และไฟล์ CA",
    "TIMEOUT": "Server ไม่ตอบกลับภายในเวลาที่กำหนด",
    "PROTOCOL": "ข้อมูลการเชื่อมต่อไม่สมบูรณ์ กรุณาเชื่อมต่อใหม่",
    "CONNECTION": "เชื่อมต่อ Server ไม่ได้ หรือการเชื่อมต่อขาดหาย",
    "EOF": "Server ปิดการเชื่อมต่อ",
    "STOPPED": "ตัดการเชื่อมต่อแล้ว",
}


class ClientController:
    def __init__(self, on_change=lambda: None):
        self.state = Session()
        self.on_change = on_change
        self.worker = None
        self.config = None
        self.phase = "disconnected"
        self.error = ""
        self.info = ""
        self.auth_busy = False
        self._after_connect = None
        self._callbacks = {}
        self.pending_sends = {}  # Request id -> (room, original text).
        self._users_revision = -1
        self.groups_loading = False
        self._groups_dirty = False
        self._opening_peers = {}
        self._room_intent = 0

    @property
    def authenticated(self):
        return self.phase == "authenticated"

    def authenticate(self, kind, config, username, password, confirm_password=""):
        if self.auth_busy or self.authenticated:
            return
        self.error = self.info = ""
        self.auth_busy = True
        data = {"username": username, "password": password}
        if kind == R.REGISTER:
            data["confirm_password"] = confirm_password
        if self.worker and self.config == config and self.phase == "connected":
            self._submit_auth(kind, data)
        else:
            if self.worker:
                self.worker.close()
            self._callbacks.clear()
            self._users_revision = -1
            self._after_connect = (kind, data)
            self.config = config
            self.phase = "connecting"
            self.worker = NetworkWorker(config).start()
        self.on_change()

    def _submit_auth(self, kind, data):
        def success(result):
            self.auth_busy = False
            if kind == R.REGISTER:
                self.info = "สมัครสมาชิกแล้ว กรุณาเข้าสู่ระบบด้วยบัญชีที่สร้าง"
            else:
                key = (self.config.host, self.config.port, str(self.config.tls_ca))
                self.state.login(result["user"], key)
                self.phase = "authenticated"
                self.request(R.USERS_LIST, {}, self._initial_users)
                self.refresh_groups()

        def failure(code):
            self.auth_busy = False
            self._error(code)

        self.request(kind, data, success, failure)

    def request(self, kind, data, success=lambda result: None, failure=None):
        failure = failure or self._error
        if not self.worker or self.phase not in ("connected", "authenticated"):
            failure("DISCONNECTED")
            return None
        try:
            request_id = self.worker.submit(kind, data)
        except (ConnectionError, ValueError):
            failure("DISCONNECTED")
            return None
        self._callbacks[request_id] = (success, failure)
        return request_id

    def _error(self, code):
        self.error = ERRORS.get(code, "ทำรายการไม่สำเร็จ กรุณาตรวจการเชื่อมต่อแล้วลองใหม่")

    def _initial_users(self, result):
        if self._users_revision < 0:
            self.state.users = result["users"]

    def refresh_groups(self):
        if not self.authenticated:
            return
        if self.groups_loading:
            self._groups_dirty = True
            return
        self.groups_loading = True
        self._groups_dirty = False
        gathered = {}

        def failed(code):
            self.groups_loading = False
            self._error(code)

        def page(after_id=0, limit=50):
            def loaded(result):
                gathered.update((room["id"], room) for room in result["groups"])
                next_id = result["next_after_id"]
                if next_id is not None:
                    page(next_id, limit)
                    return
                self.state.rooms.update(gathered)
                self.groups_loading = False
                if self._groups_dirty:
                    self.refresh_groups()
                else:
                    self._discover_private_rooms()

            def page_failed(code):
                if code == "FRAME_TOO_LARGE" and limit > 1:
                    page(after_id, max(1, limit // 2))
                else:
                    failed(code)

            self.request(R.GROUP_LIST, {"after_id": after_id, "limit": limit}, loaded, page_failed)

        page()

    def _discover_private_rooms(self):
        for room_id, messages in list(self.state.messages.items()):
            if room_id not in self.state.rooms and messages:
                message = next(iter(messages.values()))
                if message["sender_id"] != self.state.user["id"]:
                    self.open_private(message["sender_id"], select=False)

    def open_private(self, peer_id, *, select=True):
        if not self.authenticated:
            return
        if select:
            self._room_intent += 1
        intent = self._room_intent if select else None
        if peer_id in self._opening_peers:
            if select:
                self._opening_peers[peer_id] = intent
            return
        self.error = ""
        self._opening_peers[peer_id] = intent

        def loaded(result):
            requested = self._opening_peers.pop(peer_id, None)
            self._room_result(result, select=requested is not None and requested == self._room_intent)

        def failed(code):
            self._opening_peers.pop(peer_id, None)
            self._error(code)

        self.request(R.PRIVATE_ROOM_OPEN, {"peer_id": peer_id}, loaded, failed)

    def _room_result(self, result, *, select=True):
        room = result["room"]
        self.state.rooms[room["id"]] = room
        if select:
            self.state.select(room["id"])

    def create_group(self, name):
        self.error = ""
        self._room_intent += 1
        intent = self._room_intent
        self.request(R.GROUP_CREATE, {"name": name}, lambda result: self._room_result(result, select=intent == self._room_intent))
        self.on_change()

    def join_group(self, room_id):
        self.error = ""
        self._room_intent += 1
        intent = self._room_intent
        self.request(R.GROUP_JOIN, {"room_id": room_id}, lambda result: self._room_result(result, select=intent == self._room_intent))
        self.on_change()

    def select_room(self, room_id):
        self._room_intent += 1
        self.state.select(room_id)
        self.error = ""
        self.on_change()

    def send(self, room_id, text):
        if not self.authenticated or not self.state.is_member(room_id):
            self._error("FORBIDDEN")
            self.on_change()
            return
        if any(room_id == item[0] for item in self.pending_sends.values()):
            return
        if not text.strip() or "\x00" in text or len(text) > 4000 or len(text.encode("utf-8")) > 16000:
            self.error = "ข้อความต้องไม่ว่าง และยาวไม่เกิน 4,000 ตัวอักษร / 16,000 bytes"
            self.on_change()
            return
        self.state.drafts[room_id] = text
        self.state.notices.pop(room_id, None)
        self.error = ""

        def success(result):
            self.pending_sends.pop(request_id, None)
            self.state.add_message(result["message"])
            if self.state.drafts.get(room_id) == text:
                self.state.drafts[room_id] = ""

        def failed(code):
            self.pending_sends.pop(request_id, None)
            self.state.notices[room_id] = "ส่งไม่สำเร็จ ข้อความร่างยังอยู่ กรุณาตรวจแล้วส่งใหม่"
            self._error(code)

        # Failure can run synchronously when enqueueing fails.
        request_id = None
        request_id = self.request(R.MESSAGE_SEND, {"room_id": room_id, "text": text}, success, failed)
        if request_id:
            self.pending_sends[request_id] = (room_id, text)
        self.on_change()

    def logout(self):
        def finished(_result=None):
            self.close()
            self.state.clear()
            self.info = "ออกจากระบบแล้ว"
        if self.authenticated:
            self.request(R.LOGOUT, {}, finished, lambda code: finished())
        else:
            finished()
        self.on_change()

    def _disconnected(self, reason):
        self.phase = "disconnected"
        self.auth_busy = False
        self.groups_loading = False
        self._after_connect = None
        self._callbacks.clear()
        self._opening_peers.clear()
        self.state.users = []
        for room_id, _text in self.pending_sends.values():
            self.state.notices[room_id] = (
                "ยังยืนยันการส่งไม่ได้ ข้อความอาจถูกบันทึกแล้ว "
                "เก็บร่างไว้ให้ตรวจสอบก่อนส่งใหม่"
            )
        self.pending_sends.clear()
        self.error = "" if reason == "STOPPED" and self.state.user is None else DISCONNECTS.get(reason, DISCONNECTS["CONNECTION"])

    def close(self):
        if self.worker:
            self.worker.close()
        self._disconnected("STOPPED")

    def pump(self):
        """Called by Tk after(); callbacks and state mutations stay on its thread."""
        if not self.worker:
            return
        changed = False
        worker = self.worker
        for _ in range(100):
            try:
                event = worker.events.get_nowait()
            except queue.Empty:
                break
            changed = True
            if event["type"] == "connected":
                self.phase = "connected"
                if self._after_connect:
                    kind, data = self._after_connect
                    self._after_connect = None
                    self._submit_auth(kind, data)
            elif event["type"] == "disconnected":
                self._disconnected(event["reason"])
            else:
                packet = event["packet"]
                if packet["type"] == RESPONSE_TYPE:
                    callbacks = self._callbacks.pop(packet["id"], None)
                    if callbacks:
                        success, failure = callbacks
                        data = packet["data"]
                        if data["ok"]:
                            success(data["result"])
                        else:
                            failure(data["error"]["code"])
                elif self.authenticated:
                    self._event(packet)
            if self.worker is not worker:
                break
        if changed:
            self.on_change()

    def _event(self, packet):
        kind, data = packet["type"], packet["data"]
        if kind == EventType.USERS_UPDATED:
            if data["revision"] > self._users_revision:
                self._users_revision = data["revision"]
                self.state.users = data["users"]
        elif kind == EventType.GROUPS_UPDATED:
            self.refresh_groups()
        elif kind == EventType.MESSAGE_NEW:
            self.state.add_message(data)
            if data["room_id"] not in self.state.rooms:
                self.refresh_groups()
