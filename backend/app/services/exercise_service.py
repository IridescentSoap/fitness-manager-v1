from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import utcnow
from app.models import Exercise
from app.services.audit import write_audit

CATEGORIES = {"STRENGTH", "CARDIO", "STRETCH"}


def serialize_exercise(item: Exercise) -> dict:
    return {
        "id": item.id,
        "owner_user_id": item.owner_user_id,
        "name": item.name,
        "category": item.category,
        "description": item.description,
        "is_active": item.is_active,
        "is_system": item.owner_user_id is None,
    }


def list_exercises(db: Session, user_id: int, *, include_inactive: bool = False) -> dict:
    stmt = select(Exercise).where(
        or_(Exercise.owner_user_id.is_(None), Exercise.owner_user_id == user_id)
    )
    if not include_inactive:
        stmt = stmt.where(Exercise.is_active.is_(True))
    items = db.scalars(stmt.order_by(Exercise.id.asc())).all()
    items = sorted(items, key=lambda x: (0 if x.owner_user_id is None else 1, x.id))
    return {"items": [serialize_exercise(i) for i in items], "total": len(items)}


def get_exercise_for_user(db: Session, user_id: int, exercise_id: int) -> Exercise:
    item = db.get(Exercise, exercise_id)
    if item is None:
        raise AppError(404, "NOT_FOUND", "动作不存在")
    if item.owner_user_id is None:
        return item
    if item.owner_user_id != user_id:
        raise AppError(404, "NOT_FOUND", "动作不存在")
    return item


def create_exercise(
    db: Session,
    *,
    user_id: int,
    name: str,
    category: str,
    description: str | None,
) -> dict:
    name_clean = name.strip()
    if not name_clean or len(name_clean) > 100:
        raise AppError(422, "VALIDATION_ERROR", "动作名称无效")
    if category not in CATEGORIES:
        raise AppError(422, "VALIDATION_ERROR", "动作类型无效")

    exists = db.scalar(
        select(Exercise).where(
            Exercise.owner_user_id == user_id,
            Exercise.name == name_clean,
        )
    )
    if exists:
        raise AppError(409, "INVALID_STATE", "同名自定义动作已存在")

    item = Exercise(
        owner_user_id=user_id,
        name=name_clean,
        category=category,
        description=(description or "").strip() or None,
        is_active=True,
    )
    db.add(item)
    write_audit(
        db,
        actor_user_id=user_id,
        entity_type="exercise",
        entity_id="new",
        action="CREATE_EXERCISE",
        detail={"name": name_clean},
    )
    db.commit()
    db.refresh(item)
    return serialize_exercise(item)


def update_exercise(
    db: Session,
    *,
    user_id: int,
    exercise_id: int,
    name: str | None = None,
    category: str | None = None,
    description: str | None = None,
    is_active: bool | None = None,
) -> dict:
    item = get_exercise_for_user(db, user_id, exercise_id)
    if item.owner_user_id is None:
        raise AppError(403, "FORBIDDEN", "不能修改系统预置动作")
    if item.owner_user_id != user_id:
        raise AppError(404, "NOT_FOUND", "动作不存在")

    if name is not None:
        name_clean = name.strip()
        if not name_clean:
            raise AppError(422, "VALIDATION_ERROR", "动作名称无效")
        item.name = name_clean
    if category is not None:
        if category not in CATEGORIES:
            raise AppError(422, "VALIDATION_ERROR", "动作类型无效")
        item.category = category
    if description is not None:
        item.description = description.strip() or None
    if is_active is not None:
        item.is_active = is_active
    item.updated_at = utcnow()
    db.add(item)
    db.commit()
    db.refresh(item)
    return serialize_exercise(item)


def deactivate_exercise(db: Session, *, user_id: int, exercise_id: int) -> None:
    item = get_exercise_for_user(db, user_id, exercise_id)
    if item.owner_user_id is None:
        raise AppError(403, "FORBIDDEN", "不能停用系统预置动作")
    if item.owner_user_id != user_id:
        raise AppError(404, "NOT_FOUND", "动作不存在")
    item.is_active = False
    item.updated_at = utcnow()
    db.add(item)
    db.commit()
