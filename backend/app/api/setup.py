from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import client_host
from app.schemas.auth import InitializeRequest
from app.schemas.common import ApiSuccess
from app.services import auth_service

router = APIRouter(prefix="/setup", tags=["setup"])


@router.get("/status")
def setup_status(db: Session = Depends(get_db)) -> ApiSuccess[dict]:
    return ApiSuccess(data=auth_service.setup_status(db))


@router.post("/initialize", status_code=201)
def setup_initialize(
    body: InitializeRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    data, raw_session, _csrf = auth_service.initialize_admin(
        db,
        username=body.username,
        display_name=body.display_name,
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
