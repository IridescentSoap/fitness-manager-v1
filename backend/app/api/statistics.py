from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.timeutil import resolve_range
from app.models import User
from app.schemas.common import ApiSuccess
from app.services import statistics_service, weight_service

router = APIRouter(prefix="/statistics", tags=["statistics"])


@router.get("/overview")
def overview(
    response: Response,
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    start, end = resolve_range(date_from, date_to)
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=statistics_service.overview(db, user_id=user.id, date_from=start, date_to=end))


@router.get("/training")
def training(
    response: Response,
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    group_by: str = Query(default="week"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    start, end = resolve_range(date_from, date_to)
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(
        data=statistics_service.training_series(
            db, user_id=user.id, date_from=start, date_to=end, group_by=group_by
        )
    )


@router.get("/weight")
def weight(
    response: Response,
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    start, end = resolve_range(date_from, date_to)
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(
        data=weight_service.weight_summary(
            db,
            user_id=user.id,
            date_from=start,
            date_to=end,
            timezone=get_settings().app_timezone,
        )
    )
