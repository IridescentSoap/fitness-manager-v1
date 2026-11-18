from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.timeutil import resolve_range
from app.models import User
from app.schemas.common import ApiSuccess
from app.services import comparison_service

router = APIRouter(prefix="/comparison", tags=["comparison"])


@router.get("/users")
def candidate_users(
    response: Response,
    scope: str = Query(default="training"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=comparison_service.list_candidate_users(db, viewer_id=user.id, scope=scope))


@router.get("/rankings")
def rankings(
    response: Response,
    metric: str = Query(default="sessions"),
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    start, end = resolve_range(date_from, date_to)
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(
        data=comparison_service.rankings(
            db, viewer_id=user.id, metric=metric, date_from=start, date_to=end
        )
    )


@router.get("/metrics")
def metrics(
    response: Response,
    user_ids: str = Query(),
    metric: str = Query(),
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    start, end = resolve_range(date_from, date_to)
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(
        data=comparison_service.compare_metrics(
            db,
            viewer_id=user.id,
            user_ids=user_ids,
            metric=metric,
            date_from=start,
            date_to=end,
        )
    )


@router.get("/weight-trends")
def weight_trends(
    response: Response,
    user_ids: str = Query(),
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    start, end = resolve_range(date_from, date_to)
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(
        data=comparison_service.weight_trends(
            db,
            viewer_id=user.id,
            user_ids=user_ids,
            date_from=start,
            date_to=end,
        )
    )
