from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_csrf
from app.models import User
from app.schemas.auth import ProfileUpdateRequest, SharingUpdateRequest
from app.schemas.common import ApiSuccess
from app.services import settings_service

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/sharing")
def get_sharing(
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=settings_service.get_sharing(db, user.id))


@router.patch("/sharing")
def update_sharing(
    body: SharingUpdateRequest,
    response: Response,
    _auth=Depends(require_csrf),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    data = settings_service.update_sharing(
        db,
        user=user,
        share_training_stats=body.share_training_stats,
        share_weight_change=body.share_weight_change,
        share_weight_values=body.share_weight_values,
    )
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=data)


@router.patch("/profile")
def update_profile(
    body: ProfileUpdateRequest,
    response: Response,
    _auth=Depends(require_csrf),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    data = settings_service.update_profile(
        db,
        user=user,
        display_name=body.display_name,
        target_weight_kg=body.target_weight_kg,
        clear_target_weight=body.target_weight_kg is None and "target_weight_kg" in body.model_fields_set,
    )
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=data)
