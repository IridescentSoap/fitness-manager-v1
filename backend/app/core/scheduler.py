"""Lightweight in-process scheduler for daily backup (03:00) and roll-forward (00:05)."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta

from app.core.timeutil import app_tz

logger = logging.getLogger(__name__)


class AppScheduler:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="fitmanager-scheduler", daemon=True)
        self._thread.start()
        logger.info("background scheduler started")

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception:
                logger.exception("scheduler tick failed")
            # Wake often enough to hit minute boundaries; sleep is interruptible.
            self._stop.wait(20)

    def _tick(self) -> None:
        now = datetime.now(app_tz())
        # 00:05 schedule roll-forward window
        if now.hour == 0 and now.minute == 5:
            self._run_roll_forward(now.date().isoformat())
        # 03:00 daily backup window
        if now.hour == 3 and now.minute == 0:
            self._run_daily_backup(now.date().isoformat())

    def _run_daily_backup(self, day_key: str) -> None:
        from app.core import database as db_module
        from app.core.config import get_settings
        from app.services.backup_service import maybe_daily_backup

        if get_settings().app_env == "development":
            return
        marker = f"scheduler_backup_{day_key}"
        with db_module.SessionLocal() as session:
            from app.models import SystemKv
            import json
            from app.core.security import utcnow

            existing = session.get(SystemKv, marker)
            if existing is not None:
                return
            maybe_daily_backup(session)
            session.merge(
                SystemKv(key=marker, value_json=json.dumps(True), updated_at=utcnow())
            )
            session.commit()
            logger.info("scheduled daily backup completed for %s", day_key)

    def _run_roll_forward(self, day_key: str) -> None:
        from app.core import database as db_module
        from app.models import SystemKv
        from app.services.schedule_service import roll_forward_all_users
        import json
        from app.core.security import utcnow

        marker = f"scheduler_roll_{day_key}"
        with db_module.SessionLocal() as session:
            existing = session.get(SystemKv, marker)
            if existing is not None:
                return
            roll_forward_all_users(session)
            session.merge(
                SystemKv(key=marker, value_json=json.dumps(True), updated_at=utcnow())
            )
            session.commit()
            logger.info("scheduled roll-forward completed for %s", day_key)


app_scheduler = AppScheduler()


def seconds_until(hour: int, minute: int) -> float:
    """Helper for tests: seconds until next HH:MM in app timezone."""
    now = datetime.now(app_tz())
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()
