from __future__ import annotations

import threading
import time
from collections import defaultdict

from app.core.config import get_settings
from app.core.errors import AppError


class LoginRateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._failures: dict[str, list[float]] = defaultdict(list)

    def reset(self) -> None:
        with self._lock:
            self._failures.clear()

    def _key(self, username: str, host: str | None) -> str:
        return f"{username.lower()}|{host or '-'}"

    def check(self, username: str, host: str | None) -> None:
        settings = get_settings()
        key = self._key(username, host)
        now = time.monotonic()
        with self._lock:
            window = [
                ts
                for ts in self._failures[key]
                if now - ts < settings.login_lockout_seconds
            ]
            self._failures[key] = window
            if len(window) >= settings.login_max_failures:
                raise AppError(429, "RATE_LIMITED", "登录失败次数过多，请稍后再试")

    def record_failure(self, username: str, host: str | None) -> None:
        key = self._key(username, host)
        with self._lock:
            self._failures[key].append(time.monotonic())

    def clear(self, username: str, host: str | None) -> None:
        key = self._key(username, host)
        with self._lock:
            self._failures.pop(key, None)


login_rate_limiter = LoginRateLimiter()
