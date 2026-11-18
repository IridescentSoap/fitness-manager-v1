from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models import ComparisonSettings, User
from app.services.statistics_service import overview
from app.services.weight_service import weight_summary

TRAINING_METRICS = {"sessions", "days", "plan_rate", "action_rate"}
SCOPES = {
    "training": "share_training_stats",
    "weight_change": "share_weight_change",
    "weight_values": "share_weight_values",
}


def _settings(db: Session, user_id: int) -> ComparisonSettings | None:
    return db.get(ComparisonSettings, user_id)


def list_candidate_users(db: Session, *, viewer_id: int, scope: str) -> dict:
    flag = SCOPES.get(scope)
    if flag is None:
        raise AppError(422, "VALIDATION_ERROR", "无效的共享范围")
    users = db.scalars(select(User).where(User.status == "ACTIVE").order_by(User.id.asc())).all()
    items = []
    for user in users:
        settings = _settings(db, user.id)
        shared = bool(settings and getattr(settings, flag))
        if user.id == viewer_id or shared:
            items.append(
                {
                    "id": user.id,
                    "username": user.username,
                    "display_name": user.display_name,
                    "is_self": user.id == viewer_id,
                }
            )
    return {"scope": scope, "items": items}


def _require_share(db: Session, viewer_id: int, target_id: int, flag: str) -> User:
    user = db.get(User, target_id)
    if user is None or user.status != "ACTIVE":
        raise AppError(404, "NOT_FOUND", "用户不存在")
    if target_id == viewer_id:
        return user
    settings = _settings(db, target_id)
    if settings is None or not getattr(settings, flag):
        raise AppError(403, "SHARING_NOT_ALLOWED", "对方未授权该数据")
    return user


def _parse_user_ids(raw: str) -> list[int]:
    parts = [item.strip() for item in raw.split(",") if item.strip()]
    try:
        ids = [int(item) for item in parts]
    except ValueError as exc:
        raise AppError(422, "VALIDATION_ERROR", "user_ids 无效") from exc
    if len(ids) < 2 or len(ids) > 5 or len(set(ids)) != len(ids):
        raise AppError(422, "VALIDATION_ERROR", "请选择 2 到 5 个不同用户")
    return ids


def _metric_value(snapshot: dict, metric: str):
    if metric == "sessions":
        return snapshot["completed_sessions"]
    if metric == "days":
        return snapshot["training_days"]
    if metric == "plan_rate":
        return snapshot["plan_completion_rate"]
    if metric == "action_rate":
        return snapshot["action_completion_rate"]
    raise AppError(422, "VALIDATION_ERROR", "无效指标")


def rankings(db: Session, *, viewer_id: int, metric: str, date_from: date, date_to: date) -> dict:
    del viewer_id
    if metric not in TRAINING_METRICS:
        raise AppError(422, "VALIDATION_ERROR", "无效排行指标")
    users = db.scalars(select(User).where(User.status == "ACTIVE").order_by(User.id.asc())).all()
    ranked_rows = []
    unranked = []
    for user in users:
        settings = _settings(db, user.id)
        if settings is None or not settings.share_training_stats:
            continue
        snapshot = overview(db, user_id=user.id, date_from=date_from, date_to=date_to)
        value = _metric_value(snapshot, metric)
        entry = {
            "user_id": user.id,
            "display_name": user.display_name,
            "value": value,
        }
        if value is None:
            entry["label"] = "无数据"
            unranked.append(entry)
        else:
            ranked_rows.append(entry)
    ranked_rows.sort(key=lambda item: (-float(item["value"]), item["user_id"]))
    last_value = None
    last_rank = 0
    items = []
    for index, entry in enumerate(ranked_rows, start=1):
        if last_value is None or float(entry["value"]) != float(last_value):
            last_rank = index
            last_value = entry["value"]
        items.append({**entry, "rank": last_rank})
    settings = get_settings()
    return {
        "metric": metric,
        "from": date_from.isoformat(),
        "to": date_to.isoformat(),
        "timezone": settings.app_timezone,
        "items": items,
        "unranked": unranked,
    }


def compare_metrics(
    db: Session,
    *,
    viewer_id: int,
    user_ids: str,
    metric: str,
    date_from: date,
    date_to: date,
) -> dict:
    ids = _parse_user_ids(user_ids)
    settings = get_settings()
    if metric == "weight_change":
        items = []
        for user_id in ids:
            user = _require_share(db, viewer_id, user_id, "share_weight_change")
            summary = weight_summary(
                db,
                user_id=user_id,
                date_from=date_from,
                date_to=date_to,
                timezone=settings.app_timezone,
            )
            items.append(
                {
                    "user_id": user.id,
                    "display_name": user.display_name,
                    "delta_kg": summary["delta_kg"],
                    "delta_percent": summary["delta_percent"],
                }
            )
        return {
            "metric": metric,
            "from": date_from.isoformat(),
            "to": date_to.isoformat(),
            "timezone": settings.app_timezone,
            "items": items,
        }
    if metric not in TRAINING_METRICS:
        raise AppError(422, "VALIDATION_ERROR", "无效指标")
    items = []
    for user_id in ids:
        user = _require_share(db, viewer_id, user_id, "share_training_stats")
        snapshot = overview(db, user_id=user_id, date_from=date_from, date_to=date_to)
        items.append(
            {
                "user_id": user.id,
                "display_name": user.display_name,
                "value": _metric_value(snapshot, metric),
            }
        )
    return {
        "metric": metric,
        "from": date_from.isoformat(),
        "to": date_to.isoformat(),
        "timezone": settings.app_timezone,
        "items": items,
    }


def weight_trends(
    db: Session,
    *,
    viewer_id: int,
    user_ids: str,
    date_from: date,
    date_to: date,
) -> dict:
    ids = _parse_user_ids(user_ids)
    settings = get_settings()
    series = []
    for user_id in ids:
        user = _require_share(db, viewer_id, user_id, "share_weight_values")
        summary = weight_summary(
            db,
            user_id=user_id,
            date_from=date_from,
            date_to=date_to,
            timezone=settings.app_timezone,
        )
        series.append(
            {
                "user_id": user.id,
                "display_name": user.display_name,
                "points": summary["points"],
            }
        )
    return {
        "from": date_from.isoformat(),
        "to": date_to.isoformat(),
        "timezone": settings.app_timezone,
        "series": series,
        "note": "变化仅作数据对比，不代表训练效果优劣",
    }
