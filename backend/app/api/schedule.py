from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_csrf
from app.core.timeutil import assert_date_range
from app.models import User
from app.schemas.common import ApiSuccess
from app.schemas.domain import OverrideRequest
from app.services import plan_service
from app.services.schedule_service import list_schedule

router = APIRouter(prefix="/schedule", tags=["schedule"])


@router.get("")
def get_schedule(
    response: Response,
    date_from: date = Query(alias="from"),
    date_to: date = Query(alias="to"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    assert_date_range(date_from, date_to)
    items = list_schedule(db, user.id, date_from, date_to)
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data={"items": items, "from": date_from.isoformat(), "to": date_to.isoformat()})


@router.put("/overrides/{workout_date}")
def put_override(
    workout_date: date,
    body: OverrideRequest,
    response: Response,
    _auth=Depends(require_csrf),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    data = plan_service.put_override(
        db,
        user_id=user.id,
        workout_date=workout_date,
        mode=body.mode,
        title=body.title,
        exercises=[item.model_dump() for item in body.exercises],
    )
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=data)


@router.delete("/overrides/{workout_date}", status_code=204)
def delete_override(
    workout_date: date,
    _auth=Depends(require_csrf),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    plan_service.delete_override(db, user_id=user.id, workout_date=workout_date)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
