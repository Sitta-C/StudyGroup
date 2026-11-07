"""Atomic identity registry and ordered online snapshots. No socket I/O here."""

import hashlib
import secrets
import threading
import time

from shared.message_types import EventType
from shared.protocol import make_event, make_response

RESUME_TTL = 7 * 24 * 60 * 60


class SessionRegistry:
    def __init__(self, *, resume_ttl=None, clock=time.time):
        self._lock = threading.Lock()
        self._sessions = {}
        self._revision = 0
        self.resume_enabled = resume_ttl is not None
        self._resume_ttl = resume_ttl
        self._clock = clock
        # One remembered login per account. Store only the token's digest.
        self._resume = {}

    def _prune_resume(self):
        now = self._clock()
        self._resume = {key: value for key, value in self._resume.items() if value[1] > now}

    def _revoke_resume(self, user_id):
        self._resume = {key: value for key, value in self._resume.items() if value[0]["id"] != user_id}

    def _users(self):
        return [dict(c.user) for _, c in sorted(self._sessions.items())]

    def users(self):
        with self._lock:
            return self._users()

    def publish(self, packet, *, user_ids=None):
        """Queue a public event or one for authorized IDs, only to live logins.

        The handler must select content recipients using database permissions
        after a successful write. Registry lookup and logout share this lock.
        """
        with self._lock:
            recipients = self._sessions.keys() if user_ids is None else set(user_ids)
            for user_id in recipients:
                connection = self._sessions.get(user_id)
                if connection is not None:
                    connection.enqueue(packet)

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
            remembered = None
            if self.resume_enabled:
                self._prune_resume()
                token = secrets.token_urlsafe(32)
                expires_at = int(self._clock() + self._resume_ttl)
                response = make_response(response["id"], {
                    **response["data"]["result"], "resume_token": token, "expires_at": expires_at,
                })
                remembered = (hashlib.sha256(token.encode("ascii")).digest(), expires_at)
            if not connection.enqueue(response):
                return False
            if remembered is not None:
                self._revoke_resume(user["id"])
                digest, expires_at = remembered
                self._resume[digest] = (dict(user), expires_at)
            connection.user = dict(user)
            self._sessions[user["id"]] = connection
            # Response precedes this connection's first online event.
            self._publish()
            return True

    def resume(self, connection, token, request_id):
        with self._lock:
            self._prune_resume()
            remembered = self._resume.get(hashlib.sha256(token.encode("ascii")).digest())
            if not self.resume_enabled or connection.user is not None or remembered is None:
                return False
            user, expires_at = remembered
            if not connection.enqueue(make_response(request_id, {
                "user": dict(user), "resume_token": token, "expires_at": expires_at,
            })):
                return False
            old = self._sessions.get(user["id"])
            if old is not None:
                # Only possession of the current token can replace a connection.
                # request_close merely signals its owner; no network I/O here.
                old.user = None
                old.request_close()
            connection.user = dict(user)
            self._sessions[user["id"]] = connection
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
            if response is not None:
                self._revoke_resume(user["id"])
            del self._sessions[user["id"]]
            self._publish(extra=(connection,) if response is not None else ())
            return True
