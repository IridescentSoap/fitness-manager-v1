from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.core.errors import AppError


def app_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().app_timezone)


def today_business() -> date:
    return datetime.now(app_tz()).date()


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def weekday_iso(d: date) -> int:
    """Monday=1 ... Sunday=7."""
    return d.isoweekday()


def daterange(start: date, end: date):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def iso_z(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def assert_date_range(date_from: date, date_to: date) -> None:
    if date_to < date_from:
        raise AppError(422, "VALIDATION_ERROR", "to 不能早于 from")
    if (date_to - date_from).days > 365:
        raise AppError(422, "VALIDATION_ERROR", "日期范围最长 366 天")


def resolve_range(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    today = today_business()
    if date_from is None and date_to is None:
        return today.replace(day=1), today
    if date_from is None or date_to is None:
        raise AppError(422, "VALIDATION_ERROR", "from 与 to 需同时提供")
    assert_date_range(date_from, date_to)
    return date_from, date_to
