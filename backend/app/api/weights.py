from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_csrf
from app.models import User
from app.schemas.common import ApiSuccess
from app.schemas.domain import WeightCreateRequest, WeightUpdateRequest
from app.services import weight_service

router = APIRouter(prefix="/weights", tags=["weights"])


@router.get("")
def list_weights(
    response: Response,
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(
        data=weight_service.list_weights(db, user_id=user.id, date_from=date_from, date_to=date_to)
    )


@router.post("", status_code=201)
def create_weight(
    body: WeightCreateRequest,
    response: Response,
    _auth=Depends(require_csrf),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    data = weight_service.create_weight(
        db,
        user_id=user.id,
        record_date=body.record_date,
        recorded_at=body.recorded_at,
        weight_kg=body.weight_kg,
        note=body.note,
    )
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=data)


@router.patch("/{weight_id}")
def update_weight(
    weight_id: int,
    body: WeightUpdateRequest,
    response: Response,
    _auth=Depends(require_csrf),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    changes = {}
    if "record_date" in body.model_fields_set:
        changes["record_date"] = body.record_date
    if "recorded_at" in body.model_fields_set:
        changes["recorded_at"] = body.recorded_at
    if "weight_kg" in body.model_fields_set:
        changes["weight_kg"] = body.weight_kg
    if "note" in body.model_fields_set:
        changes["note"] = body.note
    data = weight_service.update_weight(db, user_id=user.id, weight_id=weight_id, changes=changes)
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=data)


@router.delete("/{weight_id}", status_code=204)
def delete_weight(
    weight_id: int,
    _auth=Depends(require_csrf),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    weight_service.delete_weight(db, user_id=user.id, weight_id=weight_id)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
