from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.errors import AppError
from app.core.security import utcnow
from app.core.timeutil import iso_z
from app.models import Exercise, ScheduleOccurrence, WorkoutExercise, WorkoutSession
from app.services.audit import write_audit
from app.services.sets_util import (
    all_sets_completed,
    apply_all_sets_completed,
    normalize_set,
    normalize_sets,
    resolve_sets,
    set_count_of_target,
    summarize_sets,
)


def _target_of(item: WorkoutExercise) -> dict:
    return json.loads(item.target_snapshot_json or "{}")


def _ensure_target_sets(target: dict, *, with_completed: bool = True) -> list[dict]:
    sets = resolve_sets(target, with_completed=with_completed)
    if with_completed and not isinstance(target.get("sets"), list):
        # Legacy rows: mirror exercise-level completed onto expanded sets only when serializing
        # fresh expansions without stored set completion flags.
        pass
    return sets


def completion_of(exercises: list[WorkoutExercise]) -> tuple[int, int, str]:
    total = 0
    done = 0
    for item in exercises:
        target = _target_of(item)
        sets = target.get("sets")
        if isinstance(sets, list) and sets:
            total += len(sets)
            done += sum(1 for row in sets if row.get("completed"))
        else:
            count = set_count_of_target(target)
            total += count
            if item.completed:
                done += count
    if total > 0 and done == total:
        result = "FULL"
    elif done == 0:
        result = "NONE"
    else:
        result = "PARTIAL"
    return done, total, result


def _load_session(db: Session, user_id: int, session_id: int) -> WorkoutSession:
    row = db.scalar(
        select(WorkoutSession)
        .where(
            WorkoutSession.id == session_id,
            WorkoutSession.user_id == user_id,
            WorkoutSession.deleted_at.is_(None),
        )
        .options(selectinload(WorkoutSession.exercises))
    )
    if row is None:
        raise AppError(404, "NOT_FOUND", "训练记录不存在")
    return row


def _serialize_exercise(item: WorkoutExercise) -> dict:
    target = _target_of(item)
    sets = resolve_sets(target, with_completed=True)
    if not isinstance(target.get("sets"), list) or not target.get("sets"):
        # Expand legacy targets; if exercise marked complete, mark all sets complete.
        if item.completed:
            sets = apply_all_sets_completed(sets, True, iso_z(item.completed_at))
    summary = summarize_sets(sets)
    target = {
        **target,
        **summary,
        "sets": sets,
        "capacity": target.get("capacity") or "",
        "note": target.get("note") or "",
        "is_extra": bool(target.get("is_extra")),
    }
    completed = all_sets_completed(sets) if sets else bool(item.completed)
    return {
        "id": item.id,
        "exercise_id": item.exercise_id,
        "name": item.exercise_name_snapshot,
        "category": item.category_snapshot,
        "sort_order": item.sort_order,
        "completed": completed,
        "completed_at": iso_z(item.completed_at),
        "target": target,
    }


def serialize_session(session: WorkoutSession) -> dict:
    exercises = sorted(session.exercises, key=lambda item: item.sort_order)
    done, total, result = completion_of(exercises)
    return {
        "id": session.id,
        "occurrence_id": session.occurrence_id,
        "workout_date": session.workout_date.isoformat(),
        "title": session.title_snapshot,
        "origin": session.origin,
        "status": session.status,
        "version": session.version,
        "submitted_at": iso_z(session.submitted_at),
        "completed_count": done,
        "total_count": total,
        "completion_result": result if session.status == "SUBMITTED" else None,
        "exercises": [_serialize_exercise(item) for item in exercises],
    }


def list_records(
    db: Session,
    *,
    user_id: int,
    date_from,
    date_to,
    page: int,
    page_size: int,
) -> dict:
    if page < 1 or page_size < 1 or page_size > 100:
        raise AppError(422, "VALIDATION_ERROR", "分页参数无效")
    stmt = (
        select(WorkoutSession)
        .where(
            WorkoutSession.user_id == user_id,
            WorkoutSession.deleted_at.is_(None),
            WorkoutSession.workout_date >= date_from,
            WorkoutSession.workout_date <= date_to,
        )
        .options(selectinload(WorkoutSession.exercises))
        .order_by(WorkoutSession.workout_date.desc(), WorkoutSession.id.desc())
    )
    rows = db.scalars(stmt).all()
    total = len(rows)
    start = (page - 1) * page_size
    items = [serialize_session(row) for row in rows[start : start + page_size]]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def get_record(db: Session, *, user_id: int, record_id: int) -> dict:
    return serialize_session(_load_session(db, user_id, record_id))


def _normalize_capacity(raw: object) -> str:
    if raw is None:
        return ""
    text = str(raw).strip()
    if len(text) > 64:
        raise AppError(422, "VALIDATION_ERROR", "容量最多 64 个字符")
    return text


def _validate_adhoc_targets(ex: dict) -> None:
    """AD_HOC uses free-text capacity; traditional targets are optional if provided."""

    def _nonneg(value: object, label: str) -> None:
        if value is None:
            return
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise AppError(422, "VALIDATION_ERROR", f"{label}无效") from exc
        if number < 0:
            raise AppError(422, "VALIDATION_ERROR", f"{label}不能为负")

    _nonneg(ex.get("target_sets"), "组数")
    _nonneg(ex.get("target_reps"), "次数")
    _nonneg(ex.get("target_weight_kg"), "目标重量")
    _nonneg(ex.get("target_duration_min"), "时长")
    _nonneg(ex.get("target_distance_km"), "距离")
    _normalize_capacity(ex.get("capacity"))


def _target_payload(snap: dict, *, is_extra: bool = False) -> dict:
    sets = resolve_sets(snap, with_completed=True)
    # New draft sets start incomplete.
    sets = apply_all_sets_completed(sets, False, None)
    summary = summarize_sets(sets)
    return {
        **summary,
        "capacity": snap.get("capacity") or "",
        "note": snap.get("note") or "",
        "is_extra": bool(snap.get("is_extra") or is_extra),
        "sets": sets,
    }


def _add_exercise_rows(
    db: Session,
    session: WorkoutSession,
    snapshots: list[dict],
    *,
    is_extra: bool = False,
) -> None:
    for snap in snapshots:
        target = _target_payload(snap, is_extra=is_extra)
        db.add(
            WorkoutExercise(
                session_id=session.id,
                exercise_id=snap.get("exercise_id"),
                exercise_name_snapshot=snap.get("name") or f"#{snap.get('exercise_id')}",
                category_snapshot=snap.get("category") or "STRENGTH",
                target_snapshot_json=json.dumps(target, ensure_ascii=False),
                sort_order=int(snap.get("sort_order") or 1),
                completed=False,
            )
        )


def _copy_exercises(db: Session, session: WorkoutSession, snapshots: list[dict]) -> None:
    session.exercises.clear()
    db.flush()
    _add_exercise_rows(db, session, snapshots, is_extra=False)


def _snapshots_from_inputs(db: Session, user_id: int, exercises: list[dict]) -> list[dict]:
    if not exercises:
        raise AppError(422, "VALIDATION_ERROR", "自主训练至少包含 1 个动作")
    out = []
    for ex in exercises:
        item = db.get(Exercise, ex["exercise_id"])
        if item is None or (
            item.owner_user_id is not None and item.owner_user_id != user_id
        ) or not item.is_active:
            raise AppError(422, "VALIDATION_ERROR", "无效动作")
        _validate_adhoc_targets(ex)
        payload = {
            "exercise_id": item.id,
            "name": item.name,
            "category": item.category,
            "sort_order": int(ex["sort_order"]),
            "target_sets": ex.get("target_sets"),
            "target_reps": ex.get("target_reps"),
            "target_weight_kg": ex.get("target_weight_kg"),
            "target_duration_min": ex.get("target_duration_min"),
            "target_distance_km": ex.get("target_distance_km"),
            "capacity": _normalize_capacity(ex.get("capacity")),
            "note": ex.get("note") or "",
            "sets": [s.model_dump() if hasattr(s, "model_dump") else s for s in (ex.get("sets") or [])]
            or None,
        }
        if not payload["sets"]:
            # Default one empty set for AD_HOC when nothing provided.
            payload["sets"] = [{"reps": None, "weight_kg": None, "duration_min": None, "distance_km": None}]
        sets = resolve_sets(payload, with_completed=True)
        summary = summarize_sets(sets)
        payload.update(summary)
        payload["sets"] = sets
        out.append(payload)
    return out


def create_draft(
    db: Session,
    *,
    user_id: int,
    occurrence_id: int | None,
    workout_date,
    title: str | None,
    exercises: list[dict] | None,
) -> dict:
    if occurrence_id is not None:
        occurrence = db.scalar(
            select(ScheduleOccurrence).where(
                ScheduleOccurrence.id == occurrence_id,
                ScheduleOccurrence.user_id == user_id,
            )
        )
        if occurrence is None or occurrence.status != "PLANNED":
            raise AppError(404, "NOT_FOUND", "计划任务不存在")
        existing = db.scalar(
            select(WorkoutSession)
            .where(WorkoutSession.occurrence_id == occurrence.id)
            .options(selectinload(WorkoutSession.exercises))
        )
        if existing is not None:
            if existing.deleted_at is not None:
                existing.deleted_at = None
                existing.status = "DRAFT"
                existing.submitted_at = None
                existing.version += 1
                existing.updated_at = utcnow()
                snaps = json.loads(occurrence.exercise_snapshot_json)
                _copy_exercises(db, existing, snaps)
                db.add(existing)
                db.commit()
                db.refresh(existing)
                return serialize_session(
                    _load_session(db, user_id, existing.id)
                )
            return serialize_session(existing)

        session = WorkoutSession(
            user_id=user_id,
            occurrence_id=occurrence.id,
            workout_date=occurrence.workout_date,
            title_snapshot=occurrence.title_snapshot,
            origin="PLAN",
            status="DRAFT",
            version=1,
        )
        db.add(session)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            existing = db.scalar(
                select(WorkoutSession)
                .where(WorkoutSession.occurrence_id == occurrence.id)
                .options(selectinload(WorkoutSession.exercises))
            )
            if existing is None or existing.deleted_at is not None:
                raise AppError(409, "INVALID_STATE", "草稿创建冲突，请重试") from None
            return serialize_session(existing)
        _copy_exercises(db, session, json.loads(occurrence.exercise_snapshot_json))
        write_audit(
            db,
            actor_user_id=user_id,
            entity_type="workout_session",
            entity_id=session.id,
            action="DRAFT",
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = db.scalar(
                select(WorkoutSession)
                .where(WorkoutSession.occurrence_id == occurrence.id)
                .options(selectinload(WorkoutSession.exercises))
            )
            if existing is None:
                raise AppError(409, "INVALID_STATE", "草稿创建冲突，请重试") from None
            return serialize_session(existing)
        return serialize_session(_load_session(db, user_id, session.id))

    if workout_date is None or not title or not str(title).strip():
        raise AppError(422, "VALIDATION_ERROR", "自主训练需要日期和标题")
    snaps = _snapshots_from_inputs(db, user_id, exercises or [])
    session = WorkoutSession(
        user_id=user_id,
        occurrence_id=None,
        workout_date=workout_date,
        title_snapshot=str(title).strip(),
        origin="AD_HOC",
        status="DRAFT",
        version=1,
    )
    db.add(session)
    db.flush()
    _copy_exercises(db, session, snaps)
    write_audit(
        db,
        actor_user_id=user_id,
        entity_type="workout_session",
        entity_id=session.id,
        action="AD_HOC_DRAFT",
    )
    db.commit()
    return serialize_session(_load_session(db, user_id, session.id))


def _conflict(session: WorkoutSession) -> AppError:
    return AppError(
        409,
        "VERSION_CONFLICT",
        "该记录已在其他设备更新",
        details={"version": session.version, "record": serialize_session(session)},
    )


def append_exercises(
    db: Session,
    *,
    user_id: int,
    record_id: int,
    expected_version: int,
    exercises: list[dict],
) -> dict:
    session = _load_session(db, user_id, record_id)
    if session.status != "DRAFT":
        raise AppError(409, "INVALID_STATE", "只有草稿可以添加动作")
    if session.version != expected_version:
        raise _conflict(session)
    snaps = _snapshots_from_inputs(db, user_id, exercises)
    max_order = max((item.sort_order for item in session.exercises), default=0)
    for index, snap in enumerate(snaps):
        snap["sort_order"] = max_order + index + 1
    # Plan drafts: appended rows are extras and do not inflate plan action denominators.
    is_extra = session.origin == "PLAN"
    _add_exercise_rows(db, session, snaps, is_extra=is_extra)
    session.version += 1
    session.updated_at = utcnow()
    db.add(session)
    write_audit(
        db,
        actor_user_id=user_id,
        entity_type="workout_session",
        entity_id=session.id,
        action="APPEND_EXERCISES",
        detail={"count": len(snaps), "is_extra": is_extra},
    )
    db.commit()
    return serialize_session(_load_session(db, user_id, record_id))


def patch_action(
    db: Session,
    *,
    user_id: int,
    record_id: int,
    action_id: int,
    expected_version: int,
    completed: bool | None = None,
    capacity: str | None = None,
    exercise_id: int | None = None,
    sets: list[dict] | None = None,
    set_index: int | None = None,
    reps: float | int | None = None,
    weight_kg: float | None = None,
    duration_min: float | int | None = None,
    distance_km: float | None = None,
    set_completed: bool | None = None,
) -> dict:
    session = _load_session(db, user_id, record_id)
    if session.status != "DRAFT":
        raise AppError(409, "INVALID_STATE", "已提交记录不能直接修改动作")
    if session.version != expected_version:
        raise _conflict(session)
    action = next((item for item in session.exercises if item.id == action_id), None)
    if action is None:
        raise AppError(404, "NOT_FOUND", "动作不存在")
    has_set_patch = any(
        value is not None
        for value in (sets, set_index, reps, weight_kg, duration_min, distance_km, set_completed)
    )
    if completed is None and capacity is None and exercise_id is None and not has_set_patch:
        raise AppError(422, "VALIDATION_ERROR", "没有可更新的字段")

    changed = False
    target = _target_of(action)
    current_sets = resolve_sets(target, with_completed=True)

    if sets is not None:
        # Preserve completion flags by index when possible.
        previous = {int(item["set_index"]): item for item in current_sets}
        rebuilt = normalize_sets(sets, with_completed=True)
        merged = []
        for row in rebuilt:
            prev = previous.get(int(row["set_index"]))
            if prev:
                row["completed"] = bool(prev.get("completed"))
                row["completed_at"] = prev.get("completed_at")
            else:
                row["completed"] = False
                row["completed_at"] = None
            merged.append(row)
        current_sets = merged
        changed = True

    if set_index is not None:
        row = next((item for item in current_sets if int(item["set_index"]) == set_index), None)
        if row is None:
            raise AppError(404, "NOT_FOUND", "组不存在")
        patched = normalize_set(
            {
                "reps": reps if reps is not None else row.get("reps"),
                "weight_kg": weight_kg if weight_kg is not None else row.get("weight_kg"),
                "duration_min": duration_min if duration_min is not None else row.get("duration_min"),
                "distance_km": distance_km if distance_km is not None else row.get("distance_km"),
            },
            set_index=set_index,
            with_completed=True,
        )
        for key in ("reps", "weight_kg", "duration_min", "distance_km"):
            if row.get(key) != patched.get(key):
                row[key] = patched.get(key)
                changed = True
        if set_completed is not None and bool(row.get("completed")) != set_completed:
            row["completed"] = set_completed
            row["completed_at"] = iso_z(utcnow()) if set_completed else None
            changed = True

    if completed is not None:
        stamp = iso_z(utcnow()) if completed else None
        current_sets = apply_all_sets_completed(current_sets, completed, stamp)
        changed = True

    if capacity is not None:
        normalized = _normalize_capacity(capacity)
        if (target.get("capacity") or "") != normalized:
            target["capacity"] = normalized
            changed = True

    if exercise_id is not None and exercise_id != action.exercise_id:
        item = db.get(Exercise, exercise_id)
        if item is None or (
            item.owner_user_id is not None and item.owner_user_id != user_id
        ) or not item.is_active:
            raise AppError(422, "VALIDATION_ERROR", "无效动作")
        action.exercise_id = item.id
        action.exercise_name_snapshot = item.name
        action.category_snapshot = item.category
        changed = True

    if not changed:
        payload = serialize_session(session)
        return {
            "record_id": session.id,
            "version": session.version,
            "action_id": action.id,
            "completed": action.completed,
            "completed_at": iso_z(action.completed_at),
            "save_state": "SAVED",
            "record": payload,
        }

    summary = summarize_sets(current_sets)
    target.update(summary)
    target["sets"] = current_sets
    action.target_snapshot_json = json.dumps(target, ensure_ascii=False)
    action.completed = all_sets_completed(current_sets)
    action.completed_at = utcnow() if action.completed else None
    action.updated_at = utcnow()
    session.version += 1
    session.updated_at = utcnow()
    db.add(action)
    db.add(session)
    db.commit()
    session = _load_session(db, user_id, record_id)
    action = next(item for item in session.exercises if item.id == action_id)
    return {
        "record_id": session.id,
        "version": session.version,
        "action_id": action.id,
        "completed": action.completed,
        "completed_at": iso_z(action.completed_at),
        "save_state": "SAVED",
        "record": serialize_session(session),
    }


def _submit_payload(session: WorkoutSession) -> dict:
    data = serialize_session(session)
    return {
        "id": session.id,
        "status": session.status,
        "completion_result": data["completion_result"],
        "completed_count": data["completed_count"],
        "total_count": data["total_count"],
        "submitted_at": data["submitted_at"],
        "version": session.version,
    }


def submit_record(db: Session, *, user_id: int, record_id: int, expected_version: int) -> dict:
    session = _load_session(db, user_id, record_id)
    if session.status == "SUBMITTED":
        if expected_version in {session.version, session.version - 1}:
            return _submit_payload(session)
        raise _conflict(session)
    if session.version != expected_version:
        raise _conflict(session)
    if not session.exercises:
        raise AppError(422, "VALIDATION_ERROR", "不允许空动作列表提交")
    session.status = "SUBMITTED"
    session.submitted_at = utcnow()
    session.version += 1
    session.updated_at = utcnow()
    db.add(session)
    write_audit(
        db,
        actor_user_id=user_id,
        entity_type="workout_session",
        entity_id=session.id,
        action="SUBMIT",
    )
    db.commit()
    return _submit_payload(_load_session(db, user_id, record_id))


def reopen_record(db: Session, *, user_id: int, record_id: int, expected_version: int) -> dict:
    session = _load_session(db, user_id, record_id)
    if session.status != "SUBMITTED":
        raise AppError(409, "INVALID_STATE", "只有已提交记录可以重新编辑")
    if session.version != expected_version:
        raise _conflict(session)
    session.status = "DRAFT"
    session.submitted_at = None
    session.version += 1
    session.updated_at = utcnow()
    db.add(session)
    write_audit(
        db,
        actor_user_id=user_id,
        entity_type="workout_session",
        entity_id=session.id,
        action="REOPEN",
    )
    db.commit()
    return serialize_session(_load_session(db, user_id, record_id))


def delete_record(db: Session, *, user_id: int, record_id: int) -> None:
    session = _load_session(db, user_id, record_id)
    session.deleted_at = utcnow()
    session.version += 1
    session.updated_at = utcnow()
    db.add(session)
    write_audit(
        db,
        actor_user_id=user_id,
        entity_type="workout_session",
        entity_id=session.id,
        action="DELETE",
    )
    db.commit()
