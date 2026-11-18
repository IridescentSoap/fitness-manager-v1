from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import (
    hash_password,
    utcnow,
    validate_password,
    validate_username,
)
from app.models import ComparisonSettings, SessionAuth, User, UserSettings
from app.services.audit import write_audit


def list_users(db: Session) -> list[dict]:
    users = db.scalars(select(User).order_by(User.id.asc())).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "display_name": u.display_name,
            "role": u.role,
            "status": u.status,
            "created_at": u.created_at.isoformat().replace("+00:00", "Z")
            if u.created_at.tzinfo
            else f"{u.created_at.isoformat()}Z",
        }
        for u in users
    ]


def create_user(
    db: Session,
    *,
    actor: User,
    username: str,
    display_name: str,
    password: str,
) -> dict:
    try:
        username_norm = validate_username(username)
        validate_password(password)
    except ValueError as exc:
        raise AppError(422, "VALIDATION_ERROR", str(exc)) from exc
    if not display_name.strip():
        raise AppError(422, "VALIDATION_ERROR", "显示名不能为空")

    exists = db.scalar(select(User).where(User.username == username_norm))
    if exists:
        raise AppError(409, "INVALID_STATE", "用户名已存在")

    user = User(
        username=username_norm,
        display_name=display_name.strip(),
        password_hash=hash_password(password),
        role="USER",
        status="ACTIVE",
        session_version=1,
    )
    db.add(user)
    db.flush()
    db.add(UserSettings(user_id=user.id))
    db.add(
        ComparisonSettings(
            user_id=user.id,
            share_training_stats=False,
            share_weight_change=False,
            share_weight_values=False,
        )
    )
    write_audit(
        db,
        actor_user_id=actor.id,
        entity_type="user",
        entity_id=user.id,
        action="CREATE_USER",
        detail={"username": user.username},
    )
    db.commit()
    db.refresh(user)
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "status": user.status,
    }


def update_user(
    db: Session,
    *,
    actor: User,
    user_id: int,
    display_name: str | None = None,
    status: str | None = None,
) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise AppError(404, "NOT_FOUND", "用户不存在")
    if user.role == "ADMIN" and status == "DISABLED":
        raise AppError(422, "VALIDATION_ERROR", "不能停用管理员账号")

    if display_name is not None:
        if not display_name.strip():
            raise AppError(422, "VALIDATION_ERROR", "显示名不能为空")
        user.display_name = display_name.strip()

    if status is not None:
        if status not in {"ACTIVE", "DISABLED"}:
            raise AppError(422, "VALIDATION_ERROR", "无效状态")
        user.status = status
        if status == "DISABLED":
            user.session_version += 1
            _delete_sessions(db, user.id)

    user.updated_at = utcnow()
    write_audit(
        db,
        actor_user_id=actor.id,
        entity_type="user",
        entity_id=user.id,
        action="UPDATE_USER",
        detail={"display_name": display_name, "status": status},
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "status": user.status,
    }


def reset_password(
    db: Session,
    *,
    actor: User,
    user_id: int,
    new_password: str,
) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise AppError(404, "NOT_FOUND", "用户不存在")
    try:
        validate_password(new_password)
    except ValueError as exc:
        raise AppError(422, "VALIDATION_ERROR", str(exc)) from exc

    user.password_hash = hash_password(new_password)
    user.session_version += 1
    user.updated_at = utcnow()
    _delete_sessions(db, user.id)
    write_audit(
        db,
        actor_user_id=actor.id,
        entity_type="user",
        entity_id=user.id,
        action="RESET_PASSWORD",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "username": user.username, "status": user.status}


def _delete_sessions(db: Session, user_id: int) -> None:
    sessions = db.scalars(select(SessionAuth).where(SessionAuth.user_id == user_id)).all()
    for item in sessions:
        db.delete(item)
