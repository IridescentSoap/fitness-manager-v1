from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_csrf
from app.models import User
from app.schemas.auth import ExerciseCreateRequest, ExerciseUpdateRequest
from app.schemas.common import ApiSuccess
from app.services import exercise_service

router = APIRouter(prefix="/exercises", tags=["exercises"])


@router.get("")
def list_exercises(
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    data = exercise_service.list_exercises(db, user.id)
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=data)


@router.get("/{exercise_id}")
def get_exercise(
    exercise_id: int,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    item = exercise_service.get_exercise_for_user(db, user.id, exercise_id)
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=exercise_service.serialize_exercise(item))


@router.post("", status_code=201)
def create_exercise(
    body: ExerciseCreateRequest,
    response: Response,
    _auth=Depends(require_csrf),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    data = exercise_service.create_exercise(
        db,
        user_id=user.id,
        name=body.name,
        category=body.category,
        description=body.description,
    )
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=data)


@router.patch("/{exercise_id}")
def update_exercise(
    exercise_id: int,
    body: ExerciseUpdateRequest,
    response: Response,
    _auth=Depends(require_csrf),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    data = exercise_service.update_exercise(
        db,
        user_id=user.id,
        exercise_id=exercise_id,
        name=body.name,
        category=body.category,
        description=body.description,
        is_active=body.is_active,
    )
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=data)


@router.delete("/{exercise_id}", status_code=204)
def delete_exercise(
    exercise_id: int,
    _auth=Depends(require_csrf),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    exercise_service.deactivate_exercise(db, user_id=user.id, exercise_id=exercise_id)
    return Response(status_code=204)
