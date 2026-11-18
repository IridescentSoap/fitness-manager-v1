from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import check_database, get_db
from app.core.deps import require_admin, require_csrf
from app.models import User
from app.schemas.common import ApiSuccess
from app.schemas.domain import RestoreBackupRequest
from app.services import backup_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/health")
def admin_health(
    response: Response,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    settings = get_settings()
    database = check_database()
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(
        data={
            "status": "ok" if database.get("status") == "ok" else "degraded",
            "version": settings.app_version,
            "database": database,
            "last_backup_at": backup_service.last_backup_at(db),
        }
    )


@router.get("/backups")
def list_backups(
    response: Response,
    _auth=Depends(require_csrf),
    _admin: User = Depends(require_admin),
) -> ApiSuccess[dict]:
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=backup_service.list_backups())


@router.post("/backups", status_code=201)
def create_backup(
    response: Response,
    _auth=Depends(require_csrf),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    data = backup_service.create_backup(db, actor_user_id=admin.id, reason="manual")
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=data)


@router.post("/backups/{backup_id}/restore")
def restore_backup(
    backup_id: str,
    body: RestoreBackupRequest,
    response: Response,
    _auth=Depends(require_csrf),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ApiSuccess[dict]:
    data = backup_service.restore_backup(
        db,
        actor_user_id=admin.id,
        backup_id=backup_id,
        confirm=body.confirm,
    )
    response.headers["Cache-Control"] = "no-store"
    return ApiSuccess(data=data)
