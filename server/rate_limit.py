"""Shared rolling-window limits survive reconnects; bounded memory, monotonic time."""

import threading
import time
from collections import deque


class AuthRateLimiter:
    def __init__(self, *, address_limit=20, account_limit=5, window=60.0,
                 max_keys=4096, clock=time.monotonic):
        if min(address_limit, account_limit, max_keys) < 1 or window <= 0:
            raise ValueError("Rate limits must be positive")
        self.address_limit = address_limit
        self.account_limit = account_limit
        self.window = window
        self.max_keys = max_keys
        self.clock = clock
        self._lock = threading.Lock()
        self._attempts = {}

    def allow(self, address, account=None):
        with self._lock:
            now = self.clock()
            for key in list(self._attempts):
                attempts = self._attempts[key]
                while attempts and attempts[0] <= now - self.window:
                    attempts.popleft()
                if not attempts:
                    del self._attempts[key]
            limits = [(('address', address), self.address_limit)]
            if account is not None:
                limits.append((('account', account), self.account_limit))
            missing = sum(key not in self._attempts for key, _ in limits)
            if len(self._attempts) + missing > self.max_keys:
                return False
            if any(len(self._attempts.get(key, ())) >= limit for key, limit in limits):
                return False
            for key, _ in limits:
                self._attempts.setdefault(key, deque()).append(now)
            return True
