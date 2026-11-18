from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin, require_csrf
from app.models import User
from app.schemas.auth import (
    AdminCreateUserRequest,
    AdminResetPasswordRequest,
    AdminUpdateUserRequest,
)
from app.schemas.common import ApiSuccess
from app.services import admin_service

router = APIRouter(prefix="/admin/users", tags=["admin"])


@router.get("")
def list_users(
    response: Response,
    _auth=Depends(require_csrf),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    del admin
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data={"items": admin_service.list_users(db)})


@router.post("", status_code=201)
def create_user(
    body: AdminCreateUserRequest,
    response: Response,
    _auth=Depends(require_csrf),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    data = admin_service.create_user(
        db,
        actor=admin,
        username=body.username,
        display_name=body.display_name,
        password=body.password,
    )
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=data)


@router.patch("/{user_id}")
def update_user(
    user_id: int,
    body: AdminUpdateUserRequest,
    response: Response,
    _auth=Depends(require_csrf),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    data = admin_service.update_user(
        db,
        actor=admin,
        user_id=user_id,
        display_name=body.display_name,
        status=body.status,
    )
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=data)


@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: int,
    body: AdminResetPasswordRequest,
    response: Response,
    _auth=Depends(require_csrf),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    data = admin_service.reset_password(
        db,
        actor=admin,
        user_id=user_id,
        new_password=body.new_password,
    )
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=data)
