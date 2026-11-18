from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_csrf
from app.core.timeutil import resolve_range
from app.models import User
from app.schemas.common import ApiSuccess
from app.schemas.domain import AppendExercisesRequest, ActionPatchRequest, DraftRequest, VersionRequest
from app.services import workout_service

router = APIRouter(prefix="/records", tags=["records"])


@router.get("")
def list_records(
    response: Response,
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    start, end = resolve_range(date_from, date_to)
    data = workout_service.list_records(
        db,
        user_id=user.id,
        date_from=start,
        date_to=end,
        page=page,
        page_size=page_size,
    )
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=data)


@router.post("/drafts", status_code=201)
def create_draft(
    body: DraftRequest,
    response: Response,
    _auth=Depends(require_csrf),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    data = workout_service.create_draft(
        db,
        user_id=user.id,
        occurrence_id=body.occurrence_id,
        workout_date=body.workout_date,
        title=body.title,
        exercises=[item.model_dump() for item in body.exercises] if body.exercises is not None else None,
    )
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=data)


@router.get("/{record_id}")
def get_record(
    record_id: int,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=workout_service.get_record(db, user_id=user.id, record_id=record_id))


@router.post("/{record_id}/exercises")
def append_exercises(
    record_id: int,
    body: AppendExercisesRequest,
    response: Response,
    _auth=Depends(require_csrf),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    data = workout_service.append_exercises(
        db,
        user_id=user.id,
        record_id=record_id,
        expected_version=body.expected_version,
        exercises=[item.model_dump() for item in body.exercises],
    )
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=data)


@router.patch("/{record_id}/actions/{action_id}")
def patch_action(
    record_id: int,
    action_id: int,
    body: ActionPatchRequest,
    response: Response,
    _auth=Depends(require_csrf),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    data = workout_service.patch_action(
        db,
        user_id=user.id,
        record_id=record_id,
        action_id=action_id,
        expected_version=body.expected_version,
        completed=body.completed,
        capacity=body.capacity,
        exercise_id=body.exercise_id,
        sets=[item.model_dump() for item in body.sets] if body.sets is not None else None,
        set_index=body.set_index,
        reps=body.reps,
        weight_kg=body.weight_kg,
        duration_min=body.duration_min,
        distance_km=body.distance_km,
        set_completed=body.set_completed,
    )
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=data)


@router.post("/{record_id}/submit")
def submit_record(
    record_id: int,
    body: VersionRequest,
    response: Response,
    _auth=Depends(require_csrf),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    data = workout_service.submit_record(
        db,
        user_id=user.id,
        record_id=record_id,
        expected_version=body.expected_version,
    )
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=data)


@router.post("/{record_id}/reopen")
def reopen_record(
    record_id: int,
    body: VersionRequest,
    response: Response,
    _auth=Depends(require_csrf),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    data = workout_service.reopen_record(
        db,
        user_id=user.id,
        record_id=record_id,
        expected_version=body.expected_version,
    )
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=data)


@router.delete("/{record_id}", status_code=204)
def delete_record(
    record_id: int,
    _auth=Depends(require_csrf),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    workout_service.delete_record(db, user_id=user.id, record_id=record_id)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
