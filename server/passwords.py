"""Argon2id with library-managed random salts; never log credentials."""

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError


def validate_password(password):
    # No trimming, case folding or Unicode normalization of passwords.
    if (
        not isinstance(password, str)
        or not 8 <= len(password) <= 128
        or len(password.encode("utf-8")) > 512
        or "\x00" in password
    ):
        raise ValueError("Password must be 8-128 characters without NUL (up to 512 UTF-8 bytes)")
    return password


class Passwords:
    def __init__(self):
        self.hasher = PasswordHasher(type=Type.ID)
        # Unknown accounts still perform verification at the same work factor.
        self._dummy = self.hasher.hash("dummy password used only for timing")

    def hash(self, password):
        return self.hasher.hash(validate_password(password))

    def verify(self, password_hash, password):
        try:
            matched = self.hasher.verify(password_hash or self._dummy, password)
            return bool(password_hash) and matched
        except (VerificationError, InvalidHashError):
            return False
