from fastapi import APIRouter

from app.core.config import get_settings
from app.core.database import check_database
from app.schemas.common import ApiSuccess, HealthData

router = APIRouter(tags=["health"])


@router.get("/health", response_model=ApiSuccess[HealthData])
def health() -> ApiSuccess[HealthData]:
    settings = get_settings()
    db_info = check_database()
    return ApiSuccess(
        data=HealthData(
            status="ok" if db_info.get("status") == "ok" else "degraded",
            version=settings.app_version,
            timezone=settings.app_timezone,
            database=db_info,
        )
    )
