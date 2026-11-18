from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import utcnow
from app.core.timeutil import app_tz, daterange, iso_z
from app.models import UserSettings, WeightRecord
from app.services.audit import write_audit


def parse_weight(value: float | Decimal | None) -> Decimal:
    if value is None:
        raise AppError(422, "VALIDATION_ERROR", "体重不能为空")
    try:
        number = Decimal(str(value))
    except Exception as exc:
        raise AppError(422, "VALIDATION_ERROR", "体重格式无效") from exc
    quantized = number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if quantized != number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP):
        raise AppError(422, "VALIDATION_ERROR", "体重最多两位小数")
    # Reject more than 2 decimal places by comparing scaled integers.
    scaled = number * 100
    if scaled != scaled.to_integral_value():
        raise AppError(422, "VALIDATION_ERROR", "体重最多两位小数")
    if quantized < Decimal("20") or quantized > Decimal("400"):
        raise AppError(422, "VALIDATION_ERROR", "体重须在 20.0~400.0 kg")
    return quantized


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise AppError(422, "VALIDATION_ERROR", "测量时间必须包含时区")
    return value.astimezone(UTC)


def _check_date_alignment(record_date: date, recorded_at: datetime) -> datetime:
    aware = _as_utc(recorded_at)
    local_date = aware.astimezone(app_tz()).date()
    if local_date != record_date:
        raise AppError(422, "VALIDATION_ERROR", "测量时间与记录日期不一致")
    return aware


def _serialize(row: WeightRecord) -> dict:
    return {
        "id": row.id,
        "record_date": row.record_date.isoformat(),
        "recorded_at": iso_z(row.recorded_at),
        "weight_kg": float(row.weight_kg),
        "note": row.note or "",
    }


def list_weights(db: Session, *, user_id: int, date_from: date | None, date_to: date | None) -> dict:
    stmt = select(WeightRecord).where(
        WeightRecord.user_id == user_id,
        WeightRecord.deleted_at.is_(None),
    )
    if date_from is not None:
        stmt = stmt.where(WeightRecord.record_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(WeightRecord.record_date <= date_to)
    rows = db.scalars(stmt.order_by(WeightRecord.record_date.asc(), WeightRecord.recorded_at.asc(), WeightRecord.id.asc())).all()
    return {"items": [_serialize(row) for row in rows]}


def create_weight(
    db: Session,
    *,
    user_id: int,
    record_date: date,
    recorded_at: datetime,
    weight_kg: float,
    note: str | None,
) -> dict:
    aware = _check_date_alignment(record_date, recorded_at)
    row = WeightRecord(
        user_id=user_id,
        record_date=record_date,
        recorded_at=aware,
        weight_kg=parse_weight(weight_kg),
        note=note or "",
    )
    db.add(row)
    write_audit(db, actor_user_id=user_id, entity_type="weight", entity_id="new", action="CREATE")
    db.commit()
    db.refresh(row)
    return _serialize(row)


def _own(db: Session, user_id: int, weight_id: int) -> WeightRecord:
    row = db.scalar(
        select(WeightRecord).where(
            WeightRecord.id == weight_id,
            WeightRecord.user_id == user_id,
            WeightRecord.deleted_at.is_(None),
        )
    )
    if row is None:
        raise AppError(404, "NOT_FOUND", "体重记录不存在")
    return row


def update_weight(
    db: Session,
    *,
    user_id: int,
    weight_id: int,
    changes: dict,
) -> dict:
    row = _own(db, user_id, weight_id)
    record_date = changes.get("record_date", row.record_date)
    recorded_at = changes.get("recorded_at", row.recorded_at)
    if "record_date" in changes or "recorded_at" in changes:
        row.recorded_at = _check_date_alignment(record_date, recorded_at)
        row.record_date = record_date
    if "weight_kg" in changes and changes["weight_kg"] is not None:
        row.weight_kg = parse_weight(changes["weight_kg"])
    if "note" in changes:
        row.note = changes["note"] or ""
    row.updated_at = utcnow()
    db.add(row)
    write_audit(db, actor_user_id=user_id, entity_type="weight", entity_id=row.id, action="UPDATE")
    db.commit()
    db.refresh(row)
    return _serialize(row)


def delete_weight(db: Session, *, user_id: int, weight_id: int) -> None:
    row = _own(db, user_id, weight_id)
    row.deleted_at = utcnow()
    row.updated_at = utcnow()
    db.add(row)
    write_audit(db, actor_user_id=user_id, entity_type="weight", entity_id=row.id, action="DELETE")
    db.commit()


def _end_of_day(rows: list[WeightRecord]) -> dict[date, WeightRecord]:
    chosen: dict[date, WeightRecord] = {}
    for row in rows:
        current = chosen.get(row.record_date)
        if current is None or (row.recorded_at, row.id) >= (current.recorded_at, current.id):
            chosen[row.record_date] = row
    return chosen


def latest_weight(db: Session, user_id: int) -> dict | None:
    rows = db.scalars(
        select(WeightRecord).where(
            WeightRecord.user_id == user_id,
            WeightRecord.deleted_at.is_(None),
        )
    ).all()
    if not rows:
        return None
    row = max(rows, key=lambda item: (item.recorded_at, item.id))
    return _serialize(row)


def weight_summary(db: Session, *, user_id: int, date_from: date, date_to: date, timezone: str) -> dict:
    rows = db.scalars(
        select(WeightRecord).where(
            WeightRecord.user_id == user_id,
            WeightRecord.deleted_at.is_(None),
            WeightRecord.record_date >= date_from,
            WeightRecord.record_date <= date_to,
        )
    ).all()
    daily = _end_of_day(rows)
    ordered = [daily[day] for day in sorted(daily)]
    delta_kg = None
    delta_percent = None
    if len(ordered) >= 2:
        start = Decimal(str(ordered[0].weight_kg))
        end = Decimal(str(ordered[-1].weight_kg))
        delta = (end - start).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        delta_kg = float(delta)
        if start > 0:
            delta_percent = float(
                ((delta * Decimal(100)) / start).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            )
    points = []
    for day in daterange(date_from, date_to):
        row = daily.get(day)
        points.append(
            {
                "date": day.isoformat(),
                "weight_kg": float(row.weight_kg) if row is not None else None,
            }
        )
    settings = db.get(UserSettings, user_id)
    target = None
    if settings is not None and settings.target_weight_kg is not None:
        target = float(settings.target_weight_kg)
    return {
        "from": date_from.isoformat(),
        "to": date_to.isoformat(),
        "timezone": timezone,
        "latest": latest_weight(db, user_id),
        "target_weight_kg": target,
        "delta_kg": delta_kg,
        "delta_percent": delta_percent,
        "points": points,
    }
