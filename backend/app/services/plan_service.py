from __future__ import annotations

import json
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import AppError
from app.core.security import utcnow
from app.core.timeutil import today_business
from app.models import (
    DateOverride,
    Exercise,
    FitnessPlan,
    PlanDay,
    PlanExercise,
    PlanRevision,
    ScheduleOccurrence,
)
from app.services.audit import write_audit
from app.services.schedule_service import (
    backfill_missing_through_today,
    occurrence_has_record,
    regenerate_forward,
    weekly_snapshot_json,
)
from app.services.sets_util import (
    parse_sets_json,
    resolve_sets,
    sets_json_dumps,
    summarize_sets,
    validate_sets_for_category,
)


def _exercise_payload(e: PlanExercise) -> dict:
    stored = parse_sets_json(e.sets_json)
    legacy = {
        "target_sets": e.target_sets,
        "target_reps": e.target_reps,
        "target_weight_kg": float(e.target_weight_kg) if e.target_weight_kg is not None else None,
        "target_duration_min": e.target_duration_min,
        "target_distance_km": float(e.target_distance_km) if e.target_distance_km is not None else None,
        "sets": stored or None,
    }
    sets = resolve_sets(legacy)
    summary = summarize_sets(sets)
    return {
        "exercise_id": e.exercise_id,
        "sort_order": e.sort_order,
        "target_sets": summary["target_sets"],
        "target_reps": summary["target_reps"],
        "target_weight_kg": summary["target_weight_kg"],
        "target_duration_min": summary["target_duration_min"],
        "target_distance_km": summary["target_distance_km"],
        "capacity": e.capacity or "",
        "sets": sets,
        "note": e.note or "",
    }


def _serialize_plan(plan: FitnessPlan) -> dict:
    days = []
    for day in sorted(plan.days, key=lambda d: d.weekday):
        days.append(
            {
                "weekday": day.weekday,
                "title": day.title,
                "is_rest": day.is_rest,
                "exercises": [
                    _exercise_payload(e)
                    for e in sorted(day.exercises, key=lambda x: x.sort_order)
                ],
            }
        )
    return {
        "id": plan.id,
        "name": plan.name,
        "status": plan.status,
        "start_date": plan.start_date.isoformat(),
        "end_date": plan.end_date.isoformat() if plan.end_date else None,
        "current_revision_id": plan.current_revision_id,
        "days": days,
    }


def list_plans(db: Session, user_id: int) -> list[dict]:
    plans = db.scalars(
        select(FitnessPlan)
        .where(FitnessPlan.user_id == user_id)
        .options(selectinload(FitnessPlan.days).selectinload(PlanDay.exercises))
        .order_by(FitnessPlan.id.desc())
    ).all()
    return [_serialize_plan(p) for p in plans]


def get_plan(db: Session, user_id: int, plan_id: int) -> FitnessPlan:
    plan = db.scalar(
        select(FitnessPlan)
        .where(FitnessPlan.id == plan_id, FitnessPlan.user_id == user_id)
        .options(selectinload(FitnessPlan.days).selectinload(PlanDay.exercises))
    )
    if plan is None:
        raise AppError(404, "NOT_FOUND", "计划不存在")
    return plan


def _validate_days(db: Session, user_id: int, days: list[dict]) -> None:
    weekdays = set()
    for day in days:
        wd = int(day["weekday"])
        if wd < 1 or wd > 7:
            raise AppError(422, "VALIDATION_ERROR", "weekday 须为 1~7")
        if wd in weekdays:
            raise AppError(422, "VALIDATION_ERROR", "同一计划 weekday 不能重复")
        weekdays.add(wd)
        is_rest = bool(day.get("is_rest"))
        exercises = day.get("exercises") or []
        if is_rest and exercises:
            raise AppError(422, "VALIDATION_ERROR", "休息日不能包含动作")
        if not is_rest and not exercises:
            raise AppError(422, "VALIDATION_ERROR", "训练日至少包含一个动作")
        for ex in exercises:
            item = db.get(Exercise, ex["exercise_id"])
            if item is None or (
                item.owner_user_id is not None and item.owner_user_id != user_id
            ) or not item.is_active:
                raise AppError(422, "VALIDATION_ERROR", f"无效动作 {ex['exercise_id']}")
            _validate_targets(item.category, ex)


def _validate_targets(category: str, ex: dict) -> None:
    def _nonneg(value: object, label: str) -> None:
        if value is None:
            return
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise AppError(422, "VALIDATION_ERROR", f"{label}无效") from exc
        if number < 0:
            raise AppError(422, "VALIDATION_ERROR", f"{label}不能为负")

    capacity = str(ex.get("capacity") or "").strip()
    if len(capacity) > 64:
        raise AppError(422, "VALIDATION_ERROR", "组数/容量最多 64 个字符")

    _nonneg(ex.get("target_sets"), "组数")
    _nonneg(ex.get("target_reps"), "次数")
    _nonneg(ex.get("target_weight_kg"), "目标重量")
    _nonneg(ex.get("target_duration_min"), "时长")
    _nonneg(ex.get("target_distance_km"), "距离")

    if isinstance(ex.get("sets"), list) and ex["sets"]:
        sets = resolve_sets(ex)
        validate_sets_for_category(category, sets)
        return
    if capacity:
        return
    if category == "STRENGTH" and (not ex.get("target_sets") or not ex.get("target_reps")):
        raise AppError(422, "VALIDATION_ERROR", "力量动作需要组数和次数，或填写组列表")
    if category == "CARDIO" and not ex.get("target_duration_min") and not ex.get("target_distance_km"):
        raise AppError(422, "VALIDATION_ERROR", "有氧动作需要时长或距离，或填写组列表")
    if category == "STRETCH" and not ex.get("target_duration_min"):
        raise AppError(422, "VALIDATION_ERROR", "拉伸动作需要时长，或填写组列表")


def _plan_exercise_row(plan_day_id: int, ex: dict) -> PlanExercise:
    sets = resolve_sets(ex)
    summary = summarize_sets(sets)
    return PlanExercise(
        plan_day_id=plan_day_id,
        exercise_id=ex["exercise_id"],
        sort_order=int(ex["sort_order"]),
        target_sets=summary["target_sets"],
        target_reps=summary["target_reps"],
        target_weight_kg=summary["target_weight_kg"],
        target_duration_min=summary["target_duration_min"],
        target_distance_km=summary["target_distance_km"],
        capacity=str(ex.get("capacity") or "").strip() or None,
        sets_json=sets_json_dumps(sets),
        note=ex.get("note") or "",
    )


def _replace_days(db: Session, plan: FitnessPlan, days: list[dict]) -> None:
    plan.days.clear()
    db.flush()
    for day in days:
        pd = PlanDay(
            plan_id=plan.id,
            weekday=int(day["weekday"]),
            title=day["title"],
            is_rest=bool(day.get("is_rest")),
        )
        db.add(pd)
        db.flush()
        if pd.is_rest:
            continue
        for ex in day.get("exercises") or []:
            db.add(_plan_exercise_row(pd.id, ex))


def create_plan(
    db: Session,
    *,
    user_id: int,
    name: str,
    start_date: date,
    end_date: date | None,
    days: list[dict],
) -> dict:
    if not name.strip():
        raise AppError(422, "VALIDATION_ERROR", "计划名称不能为空")
    if end_date is not None and end_date < start_date:
        raise AppError(422, "VALIDATION_ERROR", "结束日期不能早于开始日期")
    _validate_days(db, user_id, days)
    plan = FitnessPlan(
        user_id=user_id,
        name=name.strip(),
        status="DRAFT",
        start_date=start_date,
        end_date=end_date,
    )
    db.add(plan)
    db.flush()
    _replace_days(db, plan, days)
    write_audit(db, actor_user_id=user_id, entity_type="plan", entity_id=plan.id, action="CREATE")
    db.commit()
    return _serialize_plan(get_plan(db, user_id, plan.id))


def update_plan(
    db: Session,
    *,
    user_id: int,
    plan_id: int,
    changes: dict,
) -> dict:
    plan = get_plan(db, user_id, plan_id)
    if "name" in changes and changes["name"] is not None:
        if not str(changes["name"]).strip():
            raise AppError(422, "VALIDATION_ERROR", "计划名称不能为空")
        plan.name = str(changes["name"]).strip()
    if "start_date" in changes and changes["start_date"] is not None:
        plan.start_date = changes["start_date"]
    if "end_date" in changes:
        plan.end_date = changes["end_date"]
    if plan.end_date is not None and plan.end_date < plan.start_date:
        raise AppError(422, "VALIDATION_ERROR", "结束日期不能早于开始日期")
    if "days" in changes and changes["days"] is not None:
        _validate_days(db, user_id, changes["days"])
        _replace_days(db, plan, changes["days"])
        if plan.status == "ACTIVE":
            _create_revision_and_regen(db, plan)
    plan.updated_at = utcnow()
    db.add(plan)
    write_audit(db, actor_user_id=user_id, entity_type="plan", entity_id=plan.id, action="UPDATE")
    db.commit()
    return _serialize_plan(get_plan(db, user_id, plan.id))


def _create_revision_and_regen(db: Session, plan: FitnessPlan) -> PlanRevision:
    today = today_business()
    first = plan.current_revision_id is None
    if plan.current_revision_id:
        old = db.get(PlanRevision, plan.current_revision_id)
        if old and old.effective_until is None:
            old.effective_until = today - timedelta(days=1)
            if old.effective_until < old.effective_from:
                old.effective_until = old.effective_from
            db.add(old)
    # First activation keeps the original template for dates back to start_date
    # so downtime backfill does not invent history from a later edit.
    effective_from = plan.start_date if first else max(today, plan.start_date)
    revision = PlanRevision(
        plan_id=plan.id,
        user_id=plan.user_id,
        effective_from=effective_from,
        effective_until=None,
        weekly_snapshot_json=weekly_snapshot_json(db, plan),
    )
    db.add(revision)
    db.flush()
    plan.current_revision_id = revision.id
    db.add(plan)
    if effective_from < today:
        backfill_missing_through_today(db, plan.user_id)
    regenerate_forward(db, plan.user_id, max(effective_from, today))
    return revision


def activate_plan(db: Session, *, user_id: int, plan_id: int) -> dict:
    plan = get_plan(db, user_id, plan_id)
    existing = db.scalar(
        select(FitnessPlan).where(
            FitnessPlan.user_id == user_id,
            FitnessPlan.status == "ACTIVE",
            FitnessPlan.id != plan_id,
        )
    )
    if existing:
        raise AppError(409, "PLAN_ALREADY_ACTIVE", "已有启用中的周计划，请先停用")
    plan.status = "ACTIVE"
    plan.updated_at = utcnow()
    _create_revision_and_regen(db, plan)
    write_audit(db, actor_user_id=user_id, entity_type="plan", entity_id=plan.id, action="ACTIVATE")
    db.commit()
    return _serialize_plan(get_plan(db, user_id, plan.id))


def deactivate_plan(db: Session, *, user_id: int, plan_id: int) -> dict:
    plan = get_plan(db, user_id, plan_id)
    plan.status = "INACTIVE"
    plan.updated_at = utcnow()
    if plan.current_revision_id:
        rev = db.get(PlanRevision, plan.current_revision_id)
        if rev and rev.effective_until is None:
            rev.effective_until = today_business()
            db.add(rev)
    _cancel_future_without_records(db, user_id)
    db.add(plan)
    write_audit(
        db, actor_user_id=user_id, entity_type="plan", entity_id=plan.id, action="DEACTIVATE"
    )
    db.commit()
    return _serialize_plan(get_plan(db, user_id, plan.id))


def _cancel_future_without_records(db: Session, user_id: int) -> None:
    today = today_business()
    rows = db.scalars(
        select(ScheduleOccurrence).where(
            ScheduleOccurrence.user_id == user_id,
            ScheduleOccurrence.workout_date >= today,
            ScheduleOccurrence.status == "PLANNED",
        )
    ).all()
    for row in rows:
        if occurrence_has_record(db, row.id):
            continue
        row.status = "CANCELLED"
        row.updated_at = utcnow()
        db.add(row)


def duplicate_plan(db: Session, *, user_id: int, plan_id: int) -> dict:
    src = get_plan(db, user_id, plan_id)
    payload = _serialize_plan(src)
    return create_plan(
        db,
        user_id=user_id,
        name=f"{payload['name']} (副本)",
        start_date=date.fromisoformat(payload["start_date"]),
        end_date=date.fromisoformat(payload["end_date"]) if payload["end_date"] else None,
        days=payload["days"],
    )


def put_override(
    db: Session,
    *,
    user_id: int,
    workout_date: date,
    mode: str,
    title: str | None,
    exercises: list[dict] | None,
) -> dict:
    if mode not in {"REPLACE", "ADD", "REST"}:
        raise AppError(422, "VALIDATION_ERROR", "无效覆盖模式")
    today = today_business()
    if workout_date < today and mode in {"REST", "REPLACE"}:
        raise AppError(422, "VALIDATION_ERROR", "不能用 REST/REPLACE 回溯修改过去日期")
    if mode == "REST":
        exercises = []
    elif not exercises:
        raise AppError(422, "VALIDATION_ERROR", "REPLACE/ADD 至少包含一个动作")

    if exercises:
        for ex in exercises:
            item = db.get(Exercise, ex["exercise_id"])
            if item is None or (
                item.owner_user_id is not None and item.owner_user_id != user_id
            ) or not item.is_active:
                raise AppError(422, "VALIDATION_ERROR", "无效动作")
            _validate_targets(item.category, ex)

    row = db.scalar(
        select(DateOverride).where(
            DateOverride.user_id == user_id, DateOverride.workout_date == workout_date
        )
    )
    snap = json.dumps(exercises or [], ensure_ascii=False) if mode != "REST" else None
    if row is None:
        row = DateOverride(
            user_id=user_id,
            workout_date=workout_date,
            mode=mode,
            title=title,
            snapshot_json=snap,
        )
    else:
        row.mode = mode
        row.title = title
        row.snapshot_json = snap
        row.updated_at = utcnow()
    db.add(row)
    from app.services.schedule_service import materialize_date

    try:
        materialize_date(db, user_id, workout_date)
    except AppError:
        db.rollback()
        raise
    write_audit(
        db,
        actor_user_id=user_id,
        entity_type="date_override",
        entity_id=workout_date.isoformat(),
        action="UPSERT",
        detail={"mode": mode},
    )
    db.commit()
    return {
        "workout_date": workout_date.isoformat(),
        "mode": mode,
        "title": title,
        "exercises": exercises or [],
    }


def delete_override(db: Session, *, user_id: int, workout_date: date) -> None:
    row = db.scalar(
        select(DateOverride).where(
            DateOverride.user_id == user_id, DateOverride.workout_date == workout_date
        )
    )
    if row is None:
        raise AppError(404, "NOT_FOUND", "日期覆盖不存在")
    if workout_date < today_business():
        raise AppError(422, "VALIDATION_ERROR", "不能撤销过去日期的覆盖")
    db.delete(row)
    from app.services.schedule_service import materialize_date

    materialize_date(db, user_id, workout_date)
    write_audit(
        db,
        actor_user_id=user_id,
        entity_type="date_override",
        entity_id=workout_date.isoformat(),
        action="DELETE",
    )
    db.commit()
