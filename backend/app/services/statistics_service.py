from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.timeutil import today_business
from app.models import ScheduleOccurrence, WorkoutSession
from app.services.schedule_service import ensure_historical
from app.services.weight_service import latest_weight
from app.services.sets_util import completed_set_count, snapshot_set_total
from app.services.workout_service import completion_of


def _pct(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    value = (Decimal(numerator) * Decimal(100) / Decimal(denominator)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return float(value)


def _submitted_sessions(db: Session, user_id: int, date_from: date, date_to: date) -> list[WorkoutSession]:
    return list(
        db.scalars(
            select(WorkoutSession)
            .where(
                WorkoutSession.user_id == user_id,
                WorkoutSession.deleted_at.is_(None),
                WorkoutSession.status == "SUBMITTED",
                WorkoutSession.workout_date >= date_from,
                WorkoutSession.workout_date <= date_to,
            )
            .options(selectinload(WorkoutSession.exercises))
        ).all()
    )


def _due_occurrences(db: Session, user_id: int, date_from: date, date_to: date) -> list[ScheduleOccurrence]:
    as_of = min(date_to, today_business())
    if date_from > as_of:
        return []
    return list(
        db.scalars(
            select(ScheduleOccurrence).where(
                ScheduleOccurrence.user_id == user_id,
                ScheduleOccurrence.status == "PLANNED",
                ScheduleOccurrence.source.in_(("WEEKLY", "OVERRIDE")),
                ScheduleOccurrence.workout_date >= date_from,
                ScheduleOccurrence.workout_date <= as_of,
            )
        ).all()
    )


def overview(db: Session, *, user_id: int, date_from: date, date_to: date) -> dict:
    ensure_historical(db, user_id, date_from, date_to)
    db.commit()
    occurrences = _due_occurrences(db, user_id, date_from, date_to)
    sessions = _submitted_sessions(db, user_id, date_from, date_to)
    completed_sessions = 0
    days: set[date] = set()
    for session in sessions:
        done, _total, _result = completion_of(session.exercises)
        if done > 0:
            completed_sessions += 1
            days.add(session.workout_date)

    by_occ = {session.occurrence_id: session for session in sessions if session.occurrence_id}
    planned_full = 0
    action_done = 0
    action_total = 0
    for occurrence in occurrences:
        snapshot = json.loads(occurrence.exercise_snapshot_json or "[]")
        action_total += sum(snapshot_set_total(item) for item in snapshot)
        session = by_occ.get(occurrence.id)
        if session is None:
            continue
        # Extra manually appended actions do not affect plan action completion stats.
        planned_actions = [
            item
            for item in session.exercises
            if not json.loads(item.target_snapshot_json or "{}").get("is_extra")
        ]
        done, total, result = completion_of(planned_actions)
        for item in planned_actions:
            target = json.loads(item.target_snapshot_json or "{}")
            action_done += completed_set_count(target, exercise_completed=item.completed)
        if result == "FULL" and total > 0:
            planned_full += 1

    latest = latest_weight(db, user_id)
    settings = get_settings()
    return {
        "from": date_from.isoformat(),
        "to": date_to.isoformat(),
        "timezone": settings.app_timezone,
        "completed_sessions": completed_sessions,
        "training_days": len(days),
        "planned_due": len(occurrences),
        "planned_full": planned_full,
        "plan_completion_rate": _pct(planned_full, len(occurrences)),
        "action_completion_rate": _pct(action_done, action_total),
        "latest_weight": latest,
    }


def training_series(
    db: Session,
    *,
    user_id: int,
    date_from: date,
    date_to: date,
    group_by: str,
) -> dict:
    if group_by not in {"day", "week"}:
        from app.core.errors import AppError

        raise AppError(422, "VALIDATION_ERROR", "group_by 仅支持 day 或 week")
    data = overview(db, user_id=user_id, date_from=date_from, date_to=date_to)
    sessions = _submitted_sessions(db, user_id, date_from, date_to)
    buckets: dict[str, dict] = {}

    def bucket_key(day: date) -> str:
        if group_by == "week":
            start = day - timedelta(days=day.isoweekday() - 1)
            return start.isoformat()
        return day.isoformat()

    calendar = []
    cursor = date_from
    day_counts: dict[date, int] = {}
    freq: dict[int, dict] = {}
    for session in sessions:
        done, _total, _result = completion_of(session.exercises)
        if done <= 0:
            continue
        day_counts[session.workout_date] = day_counts.get(session.workout_date, 0) + 1
        key = bucket_key(session.workout_date)
        slot = buckets.setdefault(key, {"period": key, "sessions": 0, "training_days": set()})
        slot["sessions"] += 1
        slot["training_days"].add(session.workout_date)
        for exercise in session.exercises:
            if not exercise.completed or exercise.exercise_id is None:
                continue
            item = freq.setdefault(
                exercise.exercise_id,
                {"exercise_id": exercise.exercise_id, "name": exercise.exercise_name_snapshot, "count": 0},
            )
            item["count"] += 1
            item["name"] = exercise.exercise_name_snapshot

    while cursor <= date_to:
        calendar.append({"date": cursor.isoformat(), "sessions": day_counts.get(cursor, 0)})
        cursor += timedelta(days=1)

    series = [
        {
            "period": key,
            "sessions": value["sessions"],
            "training_days": len(value["training_days"]),
        }
        for key, value in sorted(buckets.items())
    ]
    return {
        "from": data["from"],
        "to": data["to"],
        "timezone": data["timezone"],
        "group_by": group_by,
        "series": series,
        "exercise_frequency": sorted(freq.values(), key=lambda item: (-item["count"], item["exercise_id"])),
        "calendar": calendar,
    }
