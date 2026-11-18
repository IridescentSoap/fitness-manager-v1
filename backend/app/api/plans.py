from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_csrf
from app.models import User
from app.schemas.common import ApiSuccess
from app.schemas.domain import PlanCreateRequest, PlanUpdateRequest
from app.services import plan_service

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("")
def list_plans(
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data={"items": plan_service.list_plans(db, user.id)})


@router.post("", status_code=201)
def create_plan(
    body: PlanCreateRequest,
    response: Response,
    _auth=Depends(require_csrf),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    data = plan_service.create_plan(
        db,
        user_id=user.id,
        name=body.name,
        start_date=body.start_date,
        end_date=body.end_date,
        days=[day.model_dump() for day in body.days],
    )
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=data)


@router.get("/{plan_id}")
def get_plan(
    plan_id: int,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=plan_service._serialize_plan(plan_service.get_plan(db, user.id, plan_id)))


@router.patch("/{plan_id}")
def update_plan(
    plan_id: int,
    body: PlanUpdateRequest,
    response: Response,
    _auth=Depends(require_csrf),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    changes: dict = {}
    fields = body.model_fields_set
    if "name" in fields:
        changes["name"] = body.name
    if "start_date" in fields:
        changes["start_date"] = body.start_date
    if "end_date" in fields:
        changes["end_date"] = body.end_date
    if "days" in fields and body.days is not None:
        changes["days"] = [day.model_dump() for day in body.days]
    data = plan_service.update_plan(db, user_id=user.id, plan_id=plan_id, changes=changes)
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=data)


@router.post("/{plan_id}/activate")
def activate_plan(
    plan_id: int,
    response: Response,
    _auth=Depends(require_csrf),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    data = plan_service.activate_plan(db, user_id=user.id, plan_id=plan_id)
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=data)


@router.post("/{plan_id}/deactivate")
def deactivate_plan(
    plan_id: int,
    response: Response,
    _auth=Depends(require_csrf),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    data = plan_service.deactivate_plan(db, user_id=user.id, plan_id=plan_id)
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=data)


@router.post("/{plan_id}/duplicate", status_code=201)
def duplicate_plan(
    plan_id: int,
    response: Response,
    _auth=Depends(require_csrf),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    data = plan_service.duplicate_plan(db, user_id=user.id, plan_id=plan_id)
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=data)
