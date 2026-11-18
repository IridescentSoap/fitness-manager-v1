from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import SESSION_COOKIE
from app.core.errors import AppError
from app.core.security import (
    generate_token,
    hash_password,
    hash_token,
    is_loopback_host,
    normalize_username,
    session_expiry,
    validate_password,
    validate_username,
    verify_password,
    utcnow,
)
from app.models import ComparisonSettings, SessionAuth, SystemKv, User, UserSettings
from app.services.audit import write_audit
from app.services.exercise_seed import seed_system_exercises
from app.services.rate_limit import login_rate_limiter


def _user_payload(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "status": user.status,
    }


def is_initialized(db: Session) -> bool:
    row = db.get(SystemKv, "initialized")
    if row is None:
        return False
    try:
        return bool(json.loads(row.value_json))
    except json.JSONDecodeError:
        return False


def setup_status(db: Session) -> dict:
    return {"initialized": is_initialized(db)}


def initialize_admin(
    db: Session,
    *,
    username: str,
    display_name: str,
    password: str,
    client_host: str | None,
) -> tuple[dict, str, str]:
    if not is_loopback_host(client_host):
        raise AppError(403, "FORBIDDEN", "仅允许本机环回地址执行首次初始化")
    if is_initialized(db):
        raise AppError(409, "ALREADY_INITIALIZED", "系统已初始化")

    try:
        username_norm = validate_username(username)
        validate_password(password)
    except ValueError as exc:
        raise AppError(422, "VALIDATION_ERROR", str(exc)) from exc

    if not display_name.strip():
        raise AppError(422, "VALIDATION_ERROR", "显示名不能为空")

    user = User(
        username=username_norm,
        display_name=display_name.strip(),
        password_hash=hash_password(password),
        role="ADMIN",
        status="ACTIVE",
        session_version=1,
    )
    db.add(user)
    db.flush()
    db.add(UserSettings(user_id=user.id, target_weight_kg=None))
    db.add(
        ComparisonSettings(
            user_id=user.id,
            share_training_stats=False,
            share_weight_change=False,
            share_weight_values=False,
        )
    )
    db.add(
        SystemKv(
            key="initialized",
            value_json=json.dumps(True),
            updated_at=utcnow(),
        )
    )
    seed_system_exercises(db)
    raw_session, raw_csrf, session = _create_session(db, user)
    write_audit(
        db,
        actor_user_id=user.id,
        entity_type="system",
        entity_id="initialize",
        action="INITIALIZE",
        detail={"username": user.username},
    )
    db.commit()
    db.refresh(user)
    return (
        {"user": _user_payload(user), "csrf_token": raw_csrf},
        raw_session,
        raw_csrf,
    )


def _create_session(db: Session, user: User) -> tuple[str, str, SessionAuth]:
    settings = get_settings()
    raw_session = generate_token()
    raw_csrf = generate_token(24)
    session = SessionAuth(
        id=hash_token(raw_session),
        user_id=user.id,
        session_version=user.session_version,
        expires_at=session_expiry(settings.session_idle_hours),
        csrf_token_hash=hash_token(raw_csrf),
        created_at=utcnow(),
        last_seen_at=utcnow(),
    )
    db.add(session)
    return raw_session, raw_csrf, session


def login(
    db: Session,
    *,
    username: str,
    password: str,
    client_host: str | None,
) -> tuple[dict, str, str]:
    username_norm = normalize_username(username)
    login_rate_limiter.check(username_norm, client_host)

    user = db.scalar(select(User).where(User.username == username_norm))
    if (
        user is None
        or user.status != "ACTIVE"
        or not verify_password(user.password_hash, password)
    ):
        login_rate_limiter.record_failure(username_norm, client_host)
        raise AppError(401, "UNAUTHENTICATED", "用户名或密码错误")

    login_rate_limiter.clear(username_norm, client_host)
    raw_session, raw_csrf, _session = _create_session(db, user)
    write_audit(
        db,
        actor_user_id=user.id,
        entity_type="user",
        entity_id=user.id,
        action="LOGIN",
    )
    db.commit()
    db.refresh(user)
    return {"user": _user_payload(user), "csrf_token": raw_csrf}, raw_session, raw_csrf


def logout(db: Session, session: SessionAuth) -> None:
    db.delete(session)
    db.commit()


def refresh_me(db: Session, *, user: User, session: SessionAuth) -> dict:
    """Return current user and a fresh CSRF token.

    Raw CSRF cannot be recovered from its hash, so each /me issues a new token
    and the client must replace any previously stored value.
    """
    raw_csrf = generate_token(24)
    session.csrf_token_hash = hash_token(raw_csrf)
    session.last_seen_at = utcnow()
    session.expires_at = session_expiry(get_settings().session_idle_hours)
    db.add(session)
    db.commit()
    return {
        "user": _user_payload(user),
        "csrf_token": raw_csrf,
        "session_expires_at": session.expires_at.isoformat().replace("+00:00", "Z"),
    }


def change_password(
    db: Session,
    *,
    user: User,
    old_password: str,
    new_password: str,
    current_session: SessionAuth,
) -> dict:
    if not verify_password(user.password_hash, old_password):
        raise AppError(401, "UNAUTHENTICATED", "原密码不正确")
    try:
        validate_password(new_password)
    except ValueError as exc:
        raise AppError(422, "VALIDATION_ERROR", str(exc)) from exc

    user.password_hash = hash_password(new_password)
    user.session_version += 1
    user.updated_at = utcnow()
    # Invalidate other sessions; keep current by refreshing version + tokens.
    sessions = db.scalars(select(SessionAuth).where(SessionAuth.user_id == user.id)).all()
    for item in sessions:
        if item.id != current_session.id:
            db.delete(item)

    current_session.session_version = user.session_version
    raw_csrf = generate_token(24)
    current_session.csrf_token_hash = hash_token(raw_csrf)
    current_session.expires_at = session_expiry(get_settings().session_idle_hours)
    current_session.last_seen_at = utcnow()

    write_audit(
        db,
        actor_user_id=user.id,
        entity_type="user",
        entity_id=user.id,
        action="CHANGE_PASSWORD",
    )
    db.add(user)
    db.add(current_session)
    db.commit()
    db.refresh(user)
    return {"user": _user_payload(user), "csrf_token": raw_csrf}


COOKIE_NAME = SESSION_COOKIE
