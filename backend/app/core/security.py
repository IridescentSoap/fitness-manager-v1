from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_password_hasher = PasswordHasher()
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,64}$")


def utcnow() -> datetime:
    return datetime.now(UTC)


def normalize_username(username: str) -> str:
    return username.strip().lower()


def validate_username(username: str) -> str:
    normalized = normalize_username(username)
    if not _USERNAME_RE.match(normalized):
        raise ValueError("用户名须为 3~64 位字母/数字/下划线")
    return normalized


def validate_password(password: str) -> str:
    # No strength policy: any non-empty password up to storage limit is accepted.
    if password is None or password == "":
        raise ValueError("密码不能为空")
    if len(password) > 128:
        raise ValueError("密码长度不能超过 128")
    return password


def hash_password(password: str) -> str:
    return _password_hasher.hash(validate_password(password))


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def generate_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def tokens_match(raw_token: str, token_hash: str) -> bool:
    return hmac.compare_digest(hash_token(raw_token), token_hash)


def session_expiry(idle_hours: int) -> datetime:
    return utcnow() + timedelta(hours=idle_hours)


def is_loopback_host(host: str | None) -> bool:
    if not host:
        return False
    value = host.strip().lower().strip("[]")
    return value in {"127.0.0.1", "::1", "localhost"}
