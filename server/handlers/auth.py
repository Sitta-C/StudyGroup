"""Credential handlers. Internal database rows never cross the wire."""

import re
import sqlite3

from server.database import create_user, find_user_for_login, normalize_username
from server.passwords import validate_password
from shared.message_types import ErrorCode, RequestType
from shared.protocol import make_response


class AuthError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def fields(data, expected):
    if set(data) != set(expected):
        raise AuthError(ErrorCode.INVALID_INPUT, "Missing or unexpected request fields")


class AuthHandlers:
    def __init__(self, registry, passwords, limiter, hash_slots):
        self.registry = registry
        self.passwords = passwords
        self.limiter = limiter
        self.hash_slots = hash_slots

    def handle(self, connection, db, request):
        kind, data, request_id = request["type"], request["data"], request["id"]
        if kind == RequestType.LOGOUT:
            fields(data, ())
            self.registry.logout(connection, make_response(request_id, {}))
            return
        if kind == RequestType.USERS_LIST:
            fields(data, ())
            connection.enqueue(make_response(request_id, {"users": self.registry.users()}))
            return
        if connection.user is not None:
            raise AuthError(ErrorCode.ALREADY_LOGGED_IN, "Connection is already logged in")
        if kind == RequestType.RESUME_SESSION:
            fields(data, ("resume_token",))
            if not self.limiter.allow(connection.address):
                raise AuthError(ErrorCode.RATE_LIMITED, "Too many authentication attempts; try later")
            token = data["resume_token"]
            if (not isinstance(token, str) or re.fullmatch(r"[A-Za-z0-9_-]{43}", token) is None
                    or not self.registry.resume(connection, token, request_id)):
                raise AuthError(ErrorCode.AUTH_FAILED, "Session expired or invalid; login again")
            return
        fields(data, ("username", "password", "confirm_password")
               if kind == RequestType.REGISTER else ("username", "password"))
        # Consume the address budget even for invalid input. Account keys use
        # exactly the same normalization as database uniqueness and lookup.
        try:
            normalized = normalize_username(data["username"])
        except ValueError:
            normalized = None
        if not self.limiter.allow(connection.address, normalized if kind == RequestType.LOGIN else None):
            raise AuthError(ErrorCode.RATE_LIMITED, "Too many authentication attempts; try later")
        try:
            if normalized is None:
                raise ValueError("Username must be 3-24 ASCII letters, digits or underscore")
            validate_password(data["password"])
            if kind == RequestType.REGISTER and data["password"] != data["confirm_password"]:
                raise ValueError("Passwords do not match")
        except ValueError as error:
            if kind == RequestType.LOGIN:
                raise AuthError(ErrorCode.AUTH_FAILED, "Invalid username or password") from None
            raise AuthError(ErrorCode.INVALID_INPUT, str(error)) from None
        # Bound simultaneous memory-hard operations without blocking all workers.
        if not self.hash_slots.acquire(blocking=False):
            raise AuthError(ErrorCode.RATE_LIMITED, "Authentication busy; try later")
        try:
            if kind == RequestType.REGISTER:
                password_hash = self.passwords.hash(data["password"])
                try:
                    row = create_user(db, data["username"], password_hash)
                except sqlite3.IntegrityError as error:
                    if error.sqlite_errorname == "SQLITE_CONSTRAINT_UNIQUE":
                        raise AuthError(ErrorCode.USERNAME_TAKEN, "Username is already registered") from None
                    raise
                connection.enqueue(make_response(request_id, {"user": {
                    "id": row["id"], "username": row["username"],
                }}))
                return
            row = find_user_for_login(db, data["username"])
            if not self.passwords.verify(row["password_hash"] if row else None, data["password"]):
                raise AuthError(ErrorCode.AUTH_FAILED, "Invalid username or password")
            user = {"id": row["id"], "username": row["username"]}
            if self.passwords.hasher.check_needs_rehash(row["password_hash"]):
                updated = self.passwords.hash(data["password"])
                db.execute("UPDATE users SET password_hash = ? WHERE id = ? AND password_hash = ?",
                           (updated, row["id"], row["password_hash"]))
            if not self.registry.login(connection, user, make_response(request_id, {"user": user})):
                raise AuthError(ErrorCode.ALREADY_LOGGED_IN, "Account is already logged in")
        finally:
            self.hash_slots.release()
