from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import AuthContext, client_host, get_current_auth, require_csrf
from app.schemas.auth import LoginRequest, PasswordChangeRequest
from app.schemas.common import ApiSuccess
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    data, raw_session, _csrf = auth_service.login(
        db,
        username=body.username,
        password=body.password,
        client_host=client_host(request),
    )
    response.set_cookie(
        key=auth_service.COOKIE_NAME,
        value=raw_session,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=data)


@router.get("/me")
def me(
    response: Response,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    data = auth_service.refresh_me(db, user=auth.user, session=auth.session)
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=data)


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    auth: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> None:
    auth_service.logout(db, auth.session)
    response.delete_cookie(auth_service.COOKIE_NAME, path="/")


@router.patch("/password")
def change_password(
    body: PasswordChangeRequest,
    response: Response,
    auth: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    data = auth_service.change_password(
        db,
        user=auth.user,
        old_password=body.old_password,
        new_password=body.new_password,
        current_session=auth.session,
    )
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=data)
