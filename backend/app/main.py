import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.api.admin_ops import router as admin_ops_router
from app.api.admin_users import router as admin_users_router
from app.api.auth import router as auth_router
from app.api.comparison import router as comparison_router
from app.api.exercises import router as exercises_router
from app.api.health import router as health_router
from app.api.plans import router as plans_router
from app.api.records import router as records_router
from app.api.schedule import router as schedule_router
from app.api.settings import router as settings_router
from app.api.setup import router as setup_router
from app.api.statistics import router as statistics_router
from app.api.weights import router as weights_router
from app.core import database as db
from app.core.config import get_settings
from app.core.errors import AppError, app_error_handler
from app.core.scheduler import app_scheduler
from app.services.backup_service import maybe_daily_backup
from app.services.exercise_seed import seed_system_exercises
from app.services.schedule_service import roll_forward_all_users

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    settings.app_data_dir.mkdir(parents=True, exist_ok=True)
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    # Resolve SessionLocal at runtime so tests can swap the engine safely.
    with db.SessionLocal() as session:
        seed_system_exercises(session)
        session.commit()
        try:
            roll_forward_all_users(session)
            session.commit()
        except Exception:
            logger.exception("schedule roll-forward failed")
            session.rollback()
        maybe_daily_backup(session)
    if settings.app_env != "development":
        app_scheduler.start()
    try:
        yield
    finally:
        app_scheduler.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="FitManager API",
        version=settings.app_version,
        lifespan=lifespan,
    )

    if settings.app_env == "development":
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def api_no_store(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        return response

    app.add_exception_handler(AppError, app_error_handler)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "请求参数校验失败",
                    "details": {"errors": exc.errors()},
                }
            },
            headers={"Cache-Control": "no-store"},
        )

    app.include_router(health_router, prefix="/api")
    app.include_router(setup_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(admin_users_router, prefix="/api")
    app.include_router(admin_ops_router, prefix="/api")
    app.include_router(exercises_router, prefix="/api")
    app.include_router(settings_router, prefix="/api")
    app.include_router(plans_router, prefix="/api")
    app.include_router(schedule_router, prefix="/api")
    app.include_router(records_router, prefix="/api")
    app.include_router(weights_router, prefix="/api")
    app.include_router(statistics_router, prefix="/api")
    app.include_router(comparison_router, prefix="/api")
    _mount_spa(app)
    return app


def _mount_spa(app: FastAPI) -> None:
    settings = get_settings()
    if settings.app_env == "development":
        return
    dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if not dist.exists():
        return
    dist_root = dist.resolve()

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        candidate = (dist_root / full_path).resolve()
        try:
            candidate.relative_to(dist_root)
        except ValueError:
            return FileResponse(dist_root / "index.html")
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(dist_root / "index.html")


app = create_app()
