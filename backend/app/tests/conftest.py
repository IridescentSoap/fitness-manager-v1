import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

_TEST_ROOT = Path(__file__).resolve().parents[2] / ".pytest_data"
_TEST_ROOT.mkdir(parents=True, exist_ok=True)

os.environ["APP_ENV"] = "development"
os.environ["APP_DATA_DIR"] = str(_TEST_ROOT / "data")
os.environ["BACKUP_DIR"] = str(_TEST_ROOT / "backups")
os.environ["APP_VERSION"] = "0.1.0-t1-test"
os.environ["SESSION_IDLE_HOURS"] = "12"
os.environ["LOGIN_MAX_FAILURES"] = "5"
os.environ["LOGIN_LOCKOUT_SECONDS"] = "60"
os.environ["SCHEDULE_HORIZON_DAYS"] = "30"

from app.core import database as db_module
from app.core.config import get_settings
from app.core.database import Base
import app.models  # noqa: F401
from app.main import create_app
from app.services.exercise_seed import seed_system_exercises
from app.services.rate_limit import login_rate_limiter


def _configure_engine(db_path: Path) -> None:
    get_settings.cache_clear()
    os.environ["APP_DATA_DIR"] = str(db_path.parent)
    os.environ["BACKUP_DIR"] = str(db_path.parent / "backups")
    (db_path.parent / "backups").mkdir(parents=True, exist_ok=True)
    get_settings.cache_clear()

    engine = create_engine(
        f"sqlite:///{db_path.resolve().as_posix()}",
        connect_args={"check_same_thread": False},
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    db_module.engine = engine
    db_module.SessionLocal = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, future=True
    )


@pytest.fixture()
def client(tmp_path: Path):
    db_path = tmp_path / "fitness.db"
    _configure_engine(db_path)
    Base.metadata.drop_all(bind=db_module.engine)
    Base.metadata.create_all(bind=db_module.engine)
    with db_module.SessionLocal() as session:
        seed_system_exercises(session)
        session.commit()

    login_rate_limiter.reset()
    app = create_app()
    with TestClient(
        app,
        base_url="http://127.0.0.1",
        client=("127.0.0.1", 50000),
    ) as test_client:
        yield test_client

    db_module.engine.dispose()


@pytest.fixture()
def remote_client(client: TestClient):
    """Same DB/app wiring; non-loopback peer address for initialize checks."""
    del client
    app = create_app()
    with TestClient(
        app,
        base_url="http://192.168.1.50",
        client=("192.168.1.50", 50000),
    ) as test_client:
        yield test_client
