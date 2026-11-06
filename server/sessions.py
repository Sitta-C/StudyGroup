"""Atomic identity registry and ordered online snapshots. No socket I/O here."""

import threading

from shared.message_types import EventType
from shared.protocol import make_event


class SessionRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._sessions = {}
        self._revision = 0

    def _users(self):
        return [dict(c.user) for _, c in sorted(self._sessions.items())]

    def users(self):
        with self._lock:
            return self._users()

    def _publish(self, extra=()):
        self._revision += 1
        packet = make_event(EventType.USERS_UPDATED, {
            "users": self._users(), "revision": self._revision,
        })
        for connection in (*self._sessions.values(), *extra):
            connection.enqueue(packet)

    def login(self, connection, user, response):
        with self._lock:
            if connection.user is not None or user["id"] in self._sessions:
                return False
            if not connection.enqueue(response):
                return False
            connection.user = dict(user)
            self._sessions[user["id"]] = connection
            # Response precedes this connection's first online event.
            self._publish()
            return True

    def logout(self, connection, response=None):
        with self._lock:
            user = connection.user
            connection.user = None
            if response is not None:
                connection.enqueue(response)
            # Compare connection identity: stale cleanup cannot remove a relogin.
            if user is None or self._sessions.get(user["id"]) is not connection:
                return False
            del self._sessions[user["id"]]
            self._publish(extra=(connection,) if response is not None else ())
            return True
