from __future__ import annotations

import json
from datetime import date, timedelta

from sqlalchemy import and_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import utcnow
from app.core.timeutil import daterange, today_business, weekday_iso
from app.models import (
    DateOverride,
    FitnessPlan,
    PlanDay,
    PlanRevision,
    ScheduleOccurrence,
    WorkoutSession,
)


def _horizon_days() -> int:
    return get_settings().schedule_horizon_days


def _snapshot_from_day(day: PlanDay) -> tuple[str, list[dict]]:
    from app.services.sets_util import parse_sets_json, resolve_sets, summarize_sets

    exercises = sorted(day.exercises, key=lambda e: e.sort_order)
    snap = []
    for e in exercises:
        raw = {
            "exercise_id": e.exercise_id,
            "sort_order": e.sort_order,
            "target_sets": e.target_sets,
            "target_reps": e.target_reps,
            "target_weight_kg": float(e.target_weight_kg) if e.target_weight_kg is not None else None,
            "target_duration_min": e.target_duration_min,
            "target_distance_km": float(e.target_distance_km)
            if e.target_distance_km is not None
            else None,
            "capacity": e.capacity or "",
            "note": e.note or "",
            "sets": parse_sets_json(e.sets_json) or None,
        }
        sets = resolve_sets(raw)
        summary = summarize_sets(sets)
        raw.update(summary)
        raw["sets"] = sets
        snap.append(raw)
    return day.title, snap


def _enrich_snapshot(db: Session, snap: list[dict]) -> list[dict]:
    from app.models import Exercise
    from app.services.sets_util import resolve_sets, summarize_sets

    out = []
    for item in snap:
        ex = db.get(Exercise, item["exercise_id"])
        row = dict(item)
        row["name"] = ex.name if ex else f"#{item['exercise_id']}"
        row["category"] = ex.category if ex else "STRENGTH"
        sets = resolve_sets(row)
        summary = summarize_sets(sets)
        row.update(summary)
        row["sets"] = sets
        out.append(row)
    return out


def weekly_snapshot_json(db: Session, plan: FitnessPlan) -> str:
    days = []
    for day in sorted(plan.days, key=lambda d: d.weekday):
        title, snap = _snapshot_from_day(day)
        days.append(
            {
                "weekday": day.weekday,
                "title": title,
                "is_rest": day.is_rest,
                "exercises": _enrich_snapshot(db, snap),
            }
        )
    return json.dumps({"days": days}, ensure_ascii=False)


def occurrence_has_record(db: Session, occurrence_id: int) -> bool:
    session = db.scalar(
        select(WorkoutSession).where(
            WorkoutSession.occurrence_id == occurrence_id,
            WorkoutSession.deleted_at.is_(None),
        )
    )
    return session is not None


def _get_occurrence(
    db: Session, user_id: int, workout_date: date, slot: str
) -> ScheduleOccurrence | None:
    return db.scalar(
        select(ScheduleOccurrence).where(
            ScheduleOccurrence.user_id == user_id,
            ScheduleOccurrence.workout_date == workout_date,
            ScheduleOccurrence.slot == slot,
        )
    )


def _upsert_occurrence(
    db: Session,
    *,
    user_id: int,
    workout_date: date,
    slot: str,
    source: str,
    revision_id: int | None,
    title: str,
    exercises: list[dict],
    status: str = "PLANNED",
    allow_rewrite: bool = True,
) -> ScheduleOccurrence:
    existing = _get_occurrence(db, user_id, workout_date, slot)
    today = today_business()
    payload = json.dumps(exercises, ensure_ascii=False)
    if existing is not None:
        same = (
            existing.title_snapshot == title
            and existing.status == status
            and existing.source == source
            and existing.exercise_snapshot_json == payload
        )
        past = existing.workout_date < today
        has_record = occurrence_has_record(db, existing.id)
        if past:
            if not allow_rewrite and not same:
                raise AppError(409, "TASK_HAS_RECORD", "该日期任务属于历史，不能覆盖")
            return existing
        if has_record and not same:
            raise AppError(409, "TASK_HAS_RECORD", "该日期任务已有记录，不能覆盖")
        if same:
            return existing
        existing.source = source
        existing.revision_id = revision_id
        existing.title_snapshot = title
        existing.exercise_snapshot_json = payload
        existing.status = status
        existing.updated_at = utcnow()
        db.add(existing)
        return existing

    row = ScheduleOccurrence(
        user_id=user_id,
        workout_date=workout_date,
        slot=slot,
        source=source,
        revision_id=revision_id,
        title_snapshot=title,
        exercise_snapshot_json=payload,
        status=status,
    )
    db.add(row)
    db.flush()
    return row


def _cancel_slot(db: Session, user_id: int, workout_date: date, slot: str) -> None:
    existing = _get_occurrence(db, user_id, workout_date, slot)
    if existing is None:
        return
    today = today_business()
    if existing.workout_date < today or occurrence_has_record(db, existing.id):
        raise AppError(409, "TASK_HAS_RECORD", "该日期任务已有记录或属于历史，不能取消")
    existing.status = "CANCELLED"
    existing.updated_at = utcnow()
    db.add(existing)


def _day_map_from_revision(snapshot: dict) -> dict[int, dict]:
    return {int(d["weekday"]): d for d in snapshot.get("days", [])}


def _active_revision_for_date(
    db: Session, user_id: int, workout_date: date
) -> tuple[FitnessPlan | None, PlanRevision | None, dict | None]:
    plan = db.scalar(
        select(FitnessPlan)
        .where(FitnessPlan.user_id == user_id, FitnessPlan.status == "ACTIVE")
        .options(selectinload(FitnessPlan.days).selectinload(PlanDay.exercises))
    )
    if plan is None:
        return None, None, None
    if workout_date < plan.start_date:
        return plan, None, None
    if plan.end_date and workout_date > plan.end_date:
        return plan, None, None

    revision = None
    if plan.current_revision_id:
        revision = db.get(PlanRevision, plan.current_revision_id)
    if revision is None:
        return plan, None, None
    if workout_date < revision.effective_from:
        # find historical revision covering the date
        revision = db.scalar(
            select(PlanRevision)
            .where(
                PlanRevision.plan_id == plan.id,
                PlanRevision.effective_from <= workout_date,
                (PlanRevision.effective_until.is_(None))
                | (PlanRevision.effective_until >= workout_date),
            )
            .order_by(PlanRevision.effective_from.desc())
        )
    if revision is None:
        return plan, None, None
    return plan, revision, json.loads(revision.weekly_snapshot_json)


def materialize_date(db: Session, user_id: int, workout_date: date) -> None:
    """Rebuild today's/future planned occurrences for one date from plan+override."""
    today = today_business()
    if workout_date < today:
        # historical gaps filled only via revision backfill without rewriting frozen rows
        _backfill_historical_date(db, user_id, workout_date)
        return

    plan, revision, snap = _active_revision_for_date(db, user_id, workout_date)
    override = db.scalar(
        select(DateOverride).where(
            DateOverride.user_id == user_id, DateOverride.workout_date == workout_date
        )
    )

    if override and override.mode == "REST":
        _cancel_slot(db, user_id, workout_date, "BASE")
        _cancel_slot(db, user_id, workout_date, "EXTRA")
        return

    base_title = None
    base_exercises: list[dict] = []
    if snap:
        day = _day_map_from_revision(snap).get(weekday_iso(workout_date))
        if day and not day.get("is_rest"):
            base_title = day["title"]
            base_exercises = day.get("exercises") or []

    if override and override.mode == "REPLACE":
        exercises = _enrich_snapshot(db, json.loads(override.snapshot_json or "[]"))
        _upsert_occurrence(
            db,
            user_id=user_id,
            workout_date=workout_date,
            slot="BASE",
            source="OVERRIDE",
            revision_id=revision.id if revision else None,
            title=override.title or "临时训练",
            exercises=exercises,
        )
        _cancel_slot(db, user_id, workout_date, "EXTRA")
        return

    if base_title and base_exercises:
        _upsert_occurrence(
            db,
            user_id=user_id,
            workout_date=workout_date,
            slot="BASE",
            source="WEEKLY",
            revision_id=revision.id if revision else None,
            title=base_title,
            exercises=base_exercises,
        )
    else:
        # rest / no plan day
        existing = _get_occurrence(db, user_id, workout_date, "BASE")
        if existing and existing.status == "PLANNED" and not occurrence_has_record(db, existing.id):
            existing.status = "CANCELLED"
            existing.updated_at = utcnow()
            db.add(existing)

    if override and override.mode == "ADD":
        exercises = _enrich_snapshot(db, json.loads(override.snapshot_json or "[]"))
        _upsert_occurrence(
            db,
            user_id=user_id,
            workout_date=workout_date,
            slot="EXTRA",
            source="OVERRIDE",
            revision_id=revision.id if revision else None,
            title=override.title or "追加训练",
            exercises=exercises,
        )
    else:
        existing_extra = _get_occurrence(db, user_id, workout_date, "EXTRA")
        if (
            existing_extra
            and existing_extra.status == "PLANNED"
            and not occurrence_has_record(db, existing_extra.id)
        ):
            existing_extra.status = "CANCELLED"
            existing_extra.updated_at = utcnow()
            db.add(existing_extra)


def _backfill_historical_date(db: Session, user_id: int, workout_date: date) -> None:
    """Create missing historical planned occurrences from revisions if absent."""
    if _get_occurrence(db, user_id, workout_date, "BASE") or _get_occurrence(
        db, user_id, workout_date, "EXTRA"
    ):
        return
    plan, revision, snap = _active_revision_for_date(db, user_id, workout_date)
    if not snap or not revision:
        # try any revision covering date for this user
        revision = db.scalar(
            select(PlanRevision)
            .where(
                PlanRevision.user_id == user_id,
                PlanRevision.effective_from <= workout_date,
                (PlanRevision.effective_until.is_(None))
                | (PlanRevision.effective_until >= workout_date),
            )
            .order_by(PlanRevision.effective_from.desc())
        )
        if revision is None:
            return
        snap = json.loads(revision.weekly_snapshot_json)

    override = db.scalar(
        select(DateOverride).where(
            DateOverride.user_id == user_id, DateOverride.workout_date == workout_date
        )
    )
    if override and override.mode == "REST":
        return

    day = _day_map_from_revision(snap).get(weekday_iso(workout_date))
    if override and override.mode == "REPLACE":
        exercises = _enrich_snapshot(db, json.loads(override.snapshot_json or "[]"))
        _upsert_occurrence(
            db,
            user_id=user_id,
            workout_date=workout_date,
            slot="BASE",
            source="OVERRIDE",
            revision_id=revision.id,
            title=override.title or "临时训练",
            exercises=exercises,
            allow_rewrite=False,
        )
        return

    if day and not day.get("is_rest") and day.get("exercises"):
        _upsert_occurrence(
            db,
            user_id=user_id,
            workout_date=workout_date,
            slot="BASE",
            source="WEEKLY",
            revision_id=revision.id,
            title=day["title"],
            exercises=day["exercises"],
            allow_rewrite=False,
        )

    if override and override.mode == "ADD":
        exercises = _enrich_snapshot(db, json.loads(override.snapshot_json or "[]"))
        _upsert_occurrence(
            db,
            user_id=user_id,
            workout_date=workout_date,
            slot="EXTRA",
            source="OVERRIDE",
            revision_id=revision.id,
            title=override.title or "追加训练",
            exercises=exercises,
            allow_rewrite=False,
        )


def regenerate_forward(db: Session, user_id: int, from_date: date | None = None) -> None:
    today = today_business()
    start = from_date or today
    if start < today:
        start = today
    end = today + timedelta(days=_horizon_days())
    for d in daterange(start, end):
        materialize_date(db, user_id, d)


def backfill_missing_through_today(db: Session, user_id: int, lookback_days: int | None = None) -> None:
    today = today_business()
    days = lookback_days if lookback_days is not None else _horizon_days()
    start = today - timedelta(days=days)
    for d in daterange(start, today):
        _backfill_historical_date(db, user_id, d)


def ensure_historical(db: Session, user_id: int, date_from: date, date_to: date) -> None:
    """Fill missing planned rows up to today from revision history."""
    today = today_business()
    end = min(date_to, today)
    if date_from > end:
        return
    for day in daterange(date_from, end):
        _backfill_historical_date(db, user_id, day)


def roll_forward_all_users(db: Session) -> None:
    user_ids = db.scalars(select(FitnessPlan.user_id).where(FitnessPlan.status == "ACTIVE")).all()
    for uid in set(user_ids):
        backfill_missing_through_today(db, uid)
        regenerate_forward(db, uid)


def list_schedule(db: Session, user_id: int, date_from: date, date_to: date) -> list[dict]:
    if date_to < date_from:
        raise AppError(422, "VALIDATION_ERROR", "to 不能早于 from")
    if (date_to - date_from).days > 365:
        raise AppError(422, "VALIDATION_ERROR", "日期范围最长 366 天")

    # ensure near-term window materialized
    today = today_business()
    if date_to >= today:
        regenerate_forward(db, user_id, max(date_from, today))
    if date_from < today:
        for d in daterange(date_from, min(date_to, today)):
            _backfill_historical_date(db, user_id, d)
    db.commit()

    rows = db.scalars(
        select(ScheduleOccurrence)
        .where(
            ScheduleOccurrence.user_id == user_id,
            ScheduleOccurrence.workout_date >= date_from,
            ScheduleOccurrence.workout_date <= date_to,
            ScheduleOccurrence.status == "PLANNED",
        )
        .order_by(ScheduleOccurrence.workout_date.asc(), ScheduleOccurrence.slot.asc())
    ).all()

    result = []
    for row in rows:
        exercises = json.loads(row.exercise_snapshot_json)
        session = db.scalar(
            select(WorkoutSession)
            .where(
                WorkoutSession.occurrence_id == row.id,
                WorkoutSession.deleted_at.is_(None),
            )
            .options(selectinload(WorkoutSession.exercises))
        )
        record_status = None
        completion_result = None
        if session:
            record_status = session.status
            if session.status == "SUBMITTED":
                total = len(session.exercises)
                done = sum(1 for e in session.exercises if e.completed)
                if total > 0 and done == total:
                    completion_result = "FULL"
                elif done == 0:
                    completion_result = "NONE"
                else:
                    completion_result = "PARTIAL"
        result.append(
            {
                "occurrence_id": row.id,
                "workout_date": row.workout_date.isoformat(),
                "slot": row.slot,
                "source": row.source,
                "title": row.title_snapshot,
                "status": row.status,
                "actions_count": len(exercises),
                "exercises": exercises,
                "record_status": record_status,
                "completion_result": completion_result,
            }
        )
    return result
