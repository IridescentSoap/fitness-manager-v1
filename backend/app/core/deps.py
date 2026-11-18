from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import hash_token, tokens_match, utcnow
from app.models import SessionAuth, User

SESSION_COOKIE = "fm_session"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@dataclass
class AuthContext:
    user: User
    session: SessionAuth
    raw_csrf: str | None = None


def client_host(request: Request) -> str | None:
    if request.client:
        return request.client.host
    return None


def get_optional_auth(request: Request, db: Session = Depends(get_db)) -> AuthContext | None:
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        return None

    session = db.get(SessionAuth, hash_token(raw))
    if session is None:
        return None

    expires = session.expires_at
    if expires.tzinfo is None:
        from datetime import UTC

        expires = expires.replace(tzinfo=UTC)
    if expires <= utcnow():
        db.delete(session)
        db.commit()
        return None

    user = db.get(User, session.user_id)
    if user is None or user.status != "ACTIVE" or user.session_version != session.session_version:
        db.delete(session)
        db.commit()
        return None

    session.last_seen_at = utcnow()
    db.add(session)
    db.commit()
    db.refresh(session)
    return AuthContext(user=user, session=session)


def get_current_auth(auth: AuthContext | None = Depends(get_optional_auth)) -> AuthContext:
    if auth is None:
        raise AppError(401, "UNAUTHENTICATED", "未登录或会话已过期")
    return auth


def get_current_user(auth: AuthContext = Depends(get_current_auth)) -> User:
    return auth.user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "ADMIN":
        raise AppError(403, "FORBIDDEN", "需要管理员权限")
    return user


def require_csrf(
    request: Request,
    auth: AuthContext = Depends(get_current_auth),
) -> AuthContext:
    if request.method.upper() in SAFE_METHODS:
        return auth
    header = request.headers.get("X-CSRF-Token")
    if not header or not tokens_match(header, auth.session.csrf_token_hash):
        raise AppError(403, "CSRF_FAILED", "缺少或无效的 CSRF Token")
    return auth
