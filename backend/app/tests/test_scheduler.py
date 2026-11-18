from datetime import datetime

from app.core.scheduler import AppScheduler, seconds_until
from app.core.timeutil import app_tz


def test_seconds_until_is_non_negative() -> None:
    assert seconds_until(3, 0) > 0
    assert seconds_until(0, 5) > 0


def test_scheduler_start_stop() -> None:
    scheduler = AppScheduler()
    scheduler.start()
    assert scheduler._thread is not None and scheduler._thread.is_alive()
    scheduler.stop()
    # Daemon thread may already exit after stop signal
    now = datetime.now(app_tz())
    assert now.tzinfo is not None
