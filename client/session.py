"""In-memory UI state. Nothing here accesses Tk, disk, or the network."""

from dataclasses import dataclass, field


@dataclass
class Session:
    user: dict | None = None
    identity: tuple | None = None
    users: list = field(default_factory=list)
    rooms: dict = field(default_factory=dict)
    messages: dict = field(default_factory=dict)
    drafts: dict = field(default_factory=dict)
    notices: dict = field(default_factory=dict)
    unread: dict = field(default_factory=dict)
    active_room: int | None = None

    def login(self, user, server_key):
        identity = (*server_key, user["id"])
        if self.identity != identity:
            self.clear()
        self.identity = identity
        self.user = user

    def clear(self):
        self.user = None
        self.identity = None
        self.users.clear()
        self.rooms.clear()
        self.messages.clear()
        self.drafts.clear()
        self.notices.clear()
        self.unread.clear()
        self.active_room = None

    def add_message(self, message):
        room_id = message["room_id"]
        messages = self.messages.setdefault(room_id, {})
        if message["message_id"] in messages:
            return False
        messages[message["message_id"]] = message
        if room_id != self.active_room and message["sender_id"] != self.user["id"]:
            self.unread[room_id] = self.unread.get(room_id, 0) + 1
        return True

    def select(self, room_id):
        self.active_room = room_id
        self.unread.pop(room_id, None)

    def is_member(self, room_id):
        room = self.rooms.get(room_id)
        return bool(self.user and room and any(m["id"] == self.user["id"] for m in room["members"]))

    def room_title(self, room_id):
        room = self.rooms[room_id]
        if room["kind"] == "group":
            return room["name"]
        return next((m["username"] for m in room["members"] if m["id"] != self.user["id"]), "แชตส่วนตัว")
