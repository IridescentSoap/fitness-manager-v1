from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import utcnow
from app.models import ComparisonSettings, User, UserSettings
from app.services.audit import write_audit


def get_sharing(db: Session, user_id: int) -> dict:
    row = db.get(ComparisonSettings, user_id)
    if row is None:
        raise AppError(404, "NOT_FOUND", "共享设置不存在")
    return {
        "share_training_stats": bool(row.share_training_stats),
        "share_weight_change": bool(row.share_weight_change),
        "share_weight_values": bool(row.share_weight_values),
    }


def update_sharing(
    db: Session,
    *,
    user: User,
    share_training_stats: bool,
    share_weight_change: bool,
    share_weight_values: bool,
) -> dict:
    row = db.get(ComparisonSettings, user.id)
    if row is None:
        raise AppError(404, "NOT_FOUND", "共享设置不存在")
    row.share_training_stats = share_training_stats
    row.share_weight_change = share_weight_change
    row.share_weight_values = share_weight_values
    row.updated_at = utcnow()
    write_audit(
        db,
        actor_user_id=user.id,
        entity_type="comparison_settings",
        entity_id=user.id,
        action="UPDATE_SHARING",
        detail={
            "share_training_stats": share_training_stats,
            "share_weight_change": share_weight_change,
            "share_weight_values": share_weight_values,
        },
    )
    db.add(row)
    db.commit()
    return get_sharing(db, user.id)


def update_profile(
    db: Session,
    *,
    user: User,
    display_name: str | None = None,
    target_weight_kg: Decimal | float | None = None,
    clear_target_weight: bool = False,
) -> dict:
    if display_name is not None:
        if not display_name.strip():
            raise AppError(422, "VALIDATION_ERROR", "显示名不能为空")
        user.display_name = display_name.strip()
        user.updated_at = utcnow()
        db.add(user)

    settings = db.get(UserSettings, user.id)
    if settings is None:
        settings = UserSettings(user_id=user.id)
        db.add(settings)

    if clear_target_weight:
        settings.target_weight_kg = None
    elif target_weight_kg is not None:
        value = Decimal(str(target_weight_kg))
        if value < 20 or value > 400:
            raise AppError(422, "VALIDATION_ERROR", "目标体重须在 20~400 kg")
        settings.target_weight_kg = value
    settings.updated_at = utcnow()
    db.add(settings)
    db.commit()
    db.refresh(user)
    db.refresh(settings)
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "target_weight_kg": float(settings.target_weight_kg)
        if settings.target_weight_kg is not None
        else None,
    }
