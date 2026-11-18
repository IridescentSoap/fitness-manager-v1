"""T2-T6 acceptance: plans, records, statistics, comparison, backup."""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core import database as db_module
from app.core.timeutil import today_business
from app.main import create_app
from app.models import AuditLog, ScheduleOccurrence

ADMIN_PASSWORD = "AdminPass123!"
USER_PASSWORD = "UserPass1234!"
TZ = ZoneInfo("Asia/Shanghai")


def _init_admin(client: TestClient) -> dict:
    response = client.post(
        "/api/setup/initialize",
        json={"username": "admin", "display_name": "管理员", "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _login(client: TestClient, username: str, password: str) -> dict:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _csrf(token: str) -> dict[str, str]:
    return {"X-CSRF-Token": token}


def _new_client() -> TestClient:
    return TestClient(create_app(), base_url="http://127.0.0.1")


def _bootstrap_user(admin: TestClient, admin_csrf: str, username: str) -> TestClient:
    created = admin.post(
        "/api/admin/users",
        headers=_csrf(admin_csrf),
        json={"username": username, "display_name": username, "password": USER_PASSWORD},
    )
    assert created.status_code == 201, created.text
    client = _new_client()
    _login(client, username, USER_PASSWORD)
    return client


def _exercise_ids(client: TestClient) -> dict[str, dict]:
    response = client.get("/api/exercises")
    assert response.status_code == 200, response.text
    return {item["name"]: item for item in response.json()["data"]["items"]}


def _strength_targets(exercise_ids: list[int], count: int) -> list[dict]:
    return [
        {
            "exercise_id": exercise_ids[index],
            "sort_order": index + 1,
            "target_sets": 4,
            "target_reps": 8,
            "target_weight_kg": 40,
        }
        for index in range(count)
    ]


def _day(weekday: int, title: str, exercise_ids: list[int], count: int | None = None) -> dict:
    taken = exercise_ids if count is None else exercise_ids[:count]
    return {
        "weekday": weekday,
        "title": title,
        "is_rest": False,
        "exercises": _strength_targets(taken, len(taken)),
    }


def _create_plan(client: TestClient, csrf: str, *, name: str, start, days: list[dict]) -> dict:
    response = client.post(
        "/api/plans",
        headers=_csrf(csrf),
        json={"name": name, "start_date": start.isoformat(), "end_date": None, "days": days},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _activate(client: TestClient, csrf: str, plan_id: int) -> dict:
    response = client.post(f"/api/plans/{plan_id}/activate", headers=_csrf(csrf))
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _schedule(client: TestClient, start, end) -> list[dict]:
    response = client.get("/api/schedule", params={"from": start.isoformat(), "to": end.isoformat()})
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()["data"]["items"]


def _draft_occurrence(client: TestClient, csrf: str, occurrence_id: int) -> dict:
    response = client.post(
        "/api/records/drafts",
        headers=_csrf(csrf),
        json={"occurrence_id": occurrence_id},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _set_completed(client: TestClient, csrf: str, record: dict, indexes: set[int]) -> dict:
    version = record["version"]
    for index, action in enumerate(record["exercises"]):
        completed = index in indexes
        if action["completed"] == completed:
            continue
        response = client.patch(
            f"/api/records/{record['id']}/actions/{action['id']}",
            headers=_csrf(csrf),
            json={"completed": completed, "expected_version": version},
        )
        assert response.status_code == 200, response.text
        body = response.json()["data"]
        version = body["version"]
        record = body["record"]
    record["version"] = version
    return record


def _submit(client: TestClient, csrf: str, record: dict) -> dict:
    response = client.post(
        f"/api/records/{record['id']}/submit",
        headers=_csrf(csrf),
        json={"expected_version": record["version"]},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _overview(client: TestClient, start, end) -> dict:
    response = client.get("/api/statistics/overview", params={"from": start.isoformat(), "to": end.isoformat()})
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _alice(client: TestClient) -> tuple[TestClient, str]:
    _init_admin(client)
    admin = _login(client, "admin", ADMIN_PASSWORD)
    alice = _bootstrap_user(client, admin["csrf_token"], "alice")
    me = alice.get("/api/auth/me")
    return alice, me.json()["data"]["csrf_token"]


def test_t03_second_active_plan_conflicts(client: TestClient) -> None:
    alice, csrf = _alice(client)
    today = today_business()
    catalog = _exercise_ids(alice)
    bench = catalog["杠铃卧推"]["id"]
    first = _create_plan(
        alice, csrf, name="计划A", start=today, days=[_day(today.isoweekday(), "训练A", [bench])]
    )
    second = _create_plan(
        alice, csrf, name="计划B", start=today, days=[_day(today.isoweekday(), "训练B", [bench])]
    )
    _activate(alice, csrf, first["id"])
    again = alice.post(f"/api/plans/{first['id']}/activate", headers=_csrf(csrf))
    assert again.status_code == 200, again.text
    conflict = alice.post(f"/api/plans/{second['id']}/activate", headers=_csrf(csrf))
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "PLAN_ALREADY_ACTIVE"
    listed = alice.get("/api/plans")
    active = [item for item in listed.json()["data"]["items"] if item["status"] == "ACTIVE"]
    assert len(active) == 1
    assert active[0]["id"] == first["id"]
    window = _schedule(alice, today, today + timedelta(days=14))
    keys = [(item["workout_date"], item["slot"]) for item in window]
    assert len(keys) == len(set(keys))


def test_t04_monday_occurrences_are_unique(client: TestClient) -> None:
    alice, csrf = _alice(client)
    today = today_business()
    catalog = list(_exercise_ids(alice).values())
    strength = [item["id"] for item in catalog if item["category"] == "STRENGTH"][:4]
    monday = 1
    plan = _create_plan(
        alice, csrf, name="周一四动作", start=today, days=[_day(monday, "周一训练", strength, 4)]
    )
    _activate(alice, csrf, plan["id"])
    items = [
        item
        for item in _schedule(alice, today, today + timedelta(days=21))
        if item["slot"] == "BASE" and date_weekday(item["workout_date"]) == 1
    ]
    assert items
    assert all(item["actions_count"] == 4 for item in items)
    assert len({item["workout_date"] for item in items}) == len(items)
    assert items[0]["exercises"][0]["name"]


def date_weekday(value: str) -> int:
    year, month, day = (int(part) for part in value.split("-"))
    from datetime import date

    return date(year, month, day).isoweekday()


def test_t05_t06_t07_overrides(client: TestClient) -> None:
    alice, csrf = _alice(client)
    today = today_business()
    catalog = _exercise_ids(alice)
    bench = catalog["杠铃卧推"]["id"]
    swim = catalog["游泳"]["id"]
    friday = next_weekday(today, 5)
    plan = _create_plan(
        alice,
        csrf,
        name="周五计划",
        start=today,
        days=[
            _day(friday.isoweekday(), "周五力量", [bench]),
            _day(today.isoweekday(), "今日训练", [bench]),
        ]
        if friday.isoweekday() != today.isoweekday()
        else [_day(today.isoweekday(), "今日训练", [bench])],
    )
    _activate(alice, csrf, plan["id"])
    added = alice.put(
        f"/api/schedule/overrides/{friday.isoformat()}",
        headers=_csrf(csrf),
        json={
            "mode": "ADD",
            "title": "游泳训练",
            "exercises": [{"exercise_id": swim, "sort_order": 1, "target_duration_min": 40}],
        },
    )
    assert added.status_code == 200, added.text
    day_items = [
        item for item in _schedule(alice, friday, friday) if item["workout_date"] == friday.isoformat()
    ]
    slots = {item["slot"] for item in day_items}
    assert slots == {"BASE", "EXTRA"}
    following = friday + timedelta(days=7)
    if following <= today + timedelta(days=30):
        later = [
            item
            for item in _schedule(alice, following, following)
            if item["workout_date"] == following.isoformat()
        ]
        assert {item["slot"] for item in later} == {"BASE"}

    replaced = alice.put(
        f"/api/schedule/overrides/{friday.isoformat()}",
        headers=_csrf(csrf),
        json={
            "mode": "REPLACE",
            "title": "游泳训练",
            "exercises": [{"exercise_id": swim, "sort_order": 1, "target_duration_min": 40}],
        },
    )
    assert replaced.status_code == 200, replaced.text
    replaced_items = _schedule(alice, friday, friday)
    assert len(replaced_items) == 1
    assert replaced_items[0]["slot"] == "BASE"
    assert replaced_items[0]["source"] == "OVERRIDE"
    assert replaced_items[0]["title"] == "游泳训练"

    rested = alice.put(
        f"/api/schedule/overrides/{today.isoformat()}",
        headers=_csrf(csrf),
        json={"mode": "REST", "exercises": []},
    )
    assert rested.status_code == 200, rested.text
    assert _schedule(alice, today, today) == []
    next_week = today + timedelta(days=7)
    later_today = [
        item
        for item in _schedule(alice, next_week, next_week)
        if item["workout_date"] == next_week.isoformat() and item["status"] == "PLANNED"
    ]
    assert later_today


def test_t08_past_rest_rejected(client: TestClient) -> None:
    alice, csrf = _alice(client)
    today = today_business()
    past = today - timedelta(days=2)
    catalog = _exercise_ids(alice)
    bench = catalog["杠铃卧推"]["id"]
    plan = _create_plan(
        alice, csrf, name="历史计划", start=past, days=[_day(past.isoweekday(), "应完成", [bench])]
    )
    _activate(alice, csrf, plan["id"])
    before = _schedule(alice, past, past)
    assert len(before) == 1
    rejected = alice.put(
        f"/api/schedule/overrides/{past.isoformat()}",
        headers=_csrf(csrf),
        json={"mode": "REST", "exercises": []},
    )
    assert rejected.status_code == 422
    after = _schedule(alice, past, past)
    assert len(after) == 1
    assert after[0]["occurrence_id"] == before[0]["occurrence_id"]
    stats = _overview(alice, past, today)
    assert stats["planned_due"] >= 1


def test_t14_history_snapshot_frozen(client: TestClient) -> None:
    alice, csrf = _alice(client)
    today = today_business()
    past = today - timedelta(days=3)
    created = alice.post(
        "/api/exercises",
        headers=_csrf(csrf),
        json={"name": "自定义推举", "category": "STRENGTH", "description": ""},
    )
    assert created.status_code == 201, created.text
    exercise_id = created.json()["data"]["id"]
    plan = _create_plan(
        alice,
        csrf,
        name="冻结计划",
        start=past,
        days=[_day(past.isoweekday(), "旧主题", [exercise_id])],
    )
    _activate(alice, csrf, plan["id"])
    occurrence = _schedule(alice, past, past)[0]
    assert occurrence["title"] == "旧主题"
    assert occurrence["exercises"][0]["name"] == "自定义推举"
    record = _draft_occurrence(alice, csrf, occurrence["occurrence_id"])
    record = _set_completed(alice, csrf, record, {0})
    _submit(alice, csrf, record)
    renamed = alice.patch(
        f"/api/exercises/{exercise_id}",
        headers=_csrf(csrf),
        json={"name": "推举已改名"},
    )
    assert renamed.status_code == 200, renamed.text
    updated = alice.patch(
        f"/api/plans/{plan['id']}",
        headers=_csrf(csrf),
        json={"days": [_day(past.isoweekday(), "新主题", [exercise_id])]},
    )
    assert updated.status_code == 200, updated.text
    frozen = _schedule(alice, past, past)[0]
    assert frozen["title"] == "旧主题"
    assert frozen["exercises"][0]["name"] == "自定义推举"
    detail = alice.get(f"/api/records/{record['id']}")
    assert detail.status_code == 200
    assert detail.json()["data"]["exercises"][0]["name"] == "自定义推举"


def test_t29_backfill_uses_revision_history(client: TestClient) -> None:
    alice, csrf = _alice(client)
    today = today_business()
    past = today - timedelta(days=4)
    catalog = _exercise_ids(alice)
    bench = catalog["杠铃卧推"]["id"]
    plan = _create_plan(
        alice, csrf, name="修订计划", start=past, days=[_day(past.isoweekday(), "旧模板", [bench])]
    )
    _activate(alice, csrf, plan["id"])
    occurrence = _schedule(alice, past, past)[0]
    assert occurrence["title"] == "旧模板"
    updated = alice.patch(
        f"/api/plans/{plan['id']}",
        headers=_csrf(csrf),
        json={"days": [_day(past.isoweekday(), "新模板", [bench])]},
    )
    assert updated.status_code == 200, updated.text
    with db_module.SessionLocal() as db:
        row = db.get(ScheduleOccurrence, occurrence["occurrence_id"])
        assert row is not None
        db.delete(row)
        db.commit()
    restored = _schedule(alice, past, past)[0]
    assert restored["title"] == "旧模板"


def next_weekday(start, weekday: int):
    delta = (weekday - start.isoweekday()) % 7
    return start + timedelta(days=delta)


def test_records_draft_submit_reopen_and_stats(client: TestClient) -> None:
    alice, csrf = _alice(client)
    today = today_business()
    catalog = list(_exercise_ids(alice).values())
    strength = [item["id"] for item in catalog if item["category"] == "STRENGTH"][:4]
    plan = _create_plan(
        alice, csrf, name="记录计划", start=today, days=[_day(today.isoweekday(), "今日四项", strength, 4)]
    )
    _activate(alice, csrf, plan["id"])
    occurrence = _schedule(alice, today, today)[0]
    assert occurrence["actions_count"] == 4

    first = _draft_occurrence(alice, csrf, occurrence["occurrence_id"])
    second = _draft_occurrence(alice, csrf, occurrence["occurrence_id"])
    assert first["id"] == second["id"]

    partial = _set_completed(alice, csrf, first, {0, 1, 2})
    refreshed = alice.get(f"/api/records/{partial['id']}")
    assert refreshed.status_code == 200
    assert sum(1 for item in refreshed.json()["data"]["exercises"] if item["completed"]) == 3
    pending = _overview(alice, today, today)
    assert pending["completed_sessions"] == 0
    assert pending["planned_due"] >= 1
    assert pending["planned_full"] == 0
    assert pending["action_completion_rate"] == 0

    submitted = _submit(alice, csrf, partial)
    assert submitted["completion_result"] == "PARTIAL"
    partial_stats = _overview(alice, today, today)
    assert partial_stats["planned_full"] == 0
    assert partial_stats["action_completion_rate"] == pytest.approx(75)
    assert partial_stats["completed_sessions"] == 1

    reopened = alice.post(
        f"/api/records/{partial['id']}/reopen",
        headers=_csrf(csrf),
        json={"expected_version": submitted["version"]},
    )
    assert reopened.status_code == 200, reopened.text
    draft = reopened.json()["data"]
    assert draft["status"] == "DRAFT"
    full = _set_completed(alice, csrf, draft, {0, 1, 2, 3})
    full_submit = _submit(alice, csrf, full)
    assert full_submit["completion_result"] == "FULL"
    full_stats = _overview(alice, today, today)
    assert full_stats["planned_full"] == 1
    assert full_stats["plan_completion_rate"] == pytest.approx(100)

    with db_module.SessionLocal() as db:
        audit = db.scalars(select(AuditLog).where(AuditLog.action == "REOPEN")).all()
        assert audit

    none_client_record = alice.post(
        f"/api/records/{partial['id']}/reopen",
        headers=_csrf(csrf),
        json={"expected_version": full_submit["version"]},
    )
    assert none_client_record.status_code == 200
    cleared = _set_completed(alice, csrf, none_client_record.json()["data"], set())
    none_submit = _submit(alice, csrf, cleared)
    assert none_submit["completion_result"] == "NONE"
    none_stats = _overview(alice, today, today)
    assert none_stats["completed_sessions"] == 0
    assert none_stats["planned_full"] == 0


def test_edit_action_capacity_and_exercise_in_draft(client: TestClient) -> None:
    alice, csrf = _alice(client)
    today = today_business()
    catalog = _exercise_ids(alice)
    bench = catalog["杠铃卧推"]["id"]
    swim = catalog["游泳"]["id"]
    plan = _create_plan(
        alice, csrf, name="可编辑", start=today, days=[_day(today.isoweekday(), "训练日", [bench])]
    )
    _activate(alice, csrf, plan["id"])
    occurrence = _schedule(alice, today, today)[0]
    record = _draft_occurrence(alice, csrf, occurrence["occurrence_id"])
    action_id = record["exercises"][0]["id"]
    patched = alice.patch(
        f"/api/records/{record['id']}/actions/{action_id}",
        headers=_csrf(csrf),
        json={
            "expected_version": record["version"],
            "capacity": "5组",
            "exercise_id": swim,
        },
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()["data"]["record"]
    assert body["exercises"][0]["name"] == "游泳"
    assert body["exercises"][0]["target"]["capacity"] == "5组"


def test_update_plan_day_exercises_with_capacity(client: TestClient) -> None:
    alice, csrf = _alice(client)
    today = today_business()
    catalog = _exercise_ids(alice)
    bench = catalog["杠铃卧推"]["id"]
    swim = catalog["游泳"]["id"]
    plan = _create_plan(
        alice, csrf, name="可改模板", start=today, days=[_day(today.isoweekday(), "训练日", [bench])]
    )
    _activate(alice, csrf, plan["id"])
    updated = alice.patch(
        f"/api/plans/{plan['id']}",
        headers=_csrf(csrf),
        json={
            "days": [
                {
                    "weekday": today.isoweekday(),
                    "title": "上肢日",
                    "is_rest": False,
                    "exercises": [
                        {"exercise_id": bench, "sort_order": 1, "capacity": "4组"},
                        {"exercise_id": swim, "sort_order": 2, "capacity": "30分钟"},
                    ],
                }
            ]
        },
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()["data"]
    assert body["days"][0]["title"] == "上肢日"
    assert len(body["days"][0]["exercises"]) == 2
    assert body["days"][0]["exercises"][0]["capacity"] == "4组"
    assert body["days"][0]["exercises"][1]["capacity"] == "30分钟"


def test_append_exercise_to_plan_draft_with_capacity(client: TestClient) -> None:
    alice, csrf = _alice(client)
    today = today_business()
    catalog = _exercise_ids(alice)
    bench = catalog["杠铃卧推"]["id"]
    swim = catalog["游泳"]["id"]
    plan = _create_plan(
        alice, csrf, name="可追加", start=today, days=[_day(today.isoweekday(), "训练日", [bench])]
    )
    _activate(alice, csrf, plan["id"])
    occurrence = _schedule(alice, today, today)[0]
    record = _draft_occurrence(alice, csrf, occurrence["occurrence_id"])
    assert len(record["exercises"]) == 1
    appended = alice.post(
        f"/api/records/{record['id']}/exercises",
        headers=_csrf(csrf),
        json={
            "expected_version": record["version"],
            "exercises": [{"exercise_id": swim, "sort_order": 2, "capacity": "30分钟"}],
        },
    )
    assert appended.status_code == 200, appended.text
    body = appended.json()["data"]
    assert len(body["exercises"]) == 2
    assert body["exercises"][1]["name"] == "游泳"
    assert body["exercises"][1]["target"]["capacity"] == "30分钟"
    assert body["version"] == record["version"] + 1


def test_adhoc_multi_exercises_with_optional_capacity(client: TestClient) -> None:
    alice, csrf = _alice(client)
    today = today_business()
    catalog = _exercise_ids(alice)
    bench = catalog["杠铃卧推"]["id"]
    swim = catalog["游泳"]["id"]
    created = alice.post(
        "/api/records/drafts",
        headers=_csrf(csrf),
        json={
            "workout_date": today.isoformat(),
            "title": "自由综合",
            "exercises": [
                {"exercise_id": bench, "sort_order": 1, "capacity": "4x8@60kg"},
                {"exercise_id": swim, "sort_order": 2, "capacity": ""},
            ],
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()["data"]
    assert body["origin"] == "AD_HOC"
    assert len(body["exercises"]) == 2
    assert body["exercises"][0]["target"]["capacity"] == "4x8@60kg"
    assert body["exercises"][1]["target"].get("capacity", "") in ("", None)
    assert len(body["exercises"][0]["target"]["sets"]) >= 1


def test_plan_and_record_structured_sets(client: TestClient) -> None:
    alice, csrf = _alice(client)
    today = today_business()
    catalog = _exercise_ids(alice)
    bench = catalog["杠铃卧推"]["id"]
    plan = alice.post(
        "/api/plans",
        headers=_csrf(csrf),
        json={
            "name": "逐组计划",
            "start_date": today.isoformat(),
            "days": [
                {
                    "weekday": today.isoweekday(),
                    "title": "推日",
                    "is_rest": False,
                    "exercises": [
                        {
                            "exercise_id": bench,
                            "sort_order": 1,
                            "sets": [
                                {"reps": 10, "weight_kg": 60},
                                {"reps": 8, "weight_kg": 65},
                                {"reps": 6, "weight_kg": 70},
                            ],
                        }
                    ],
                }
            ],
        },
    )
    assert plan.status_code == 201, plan.text
    body = plan.json()["data"]
    sets = body["days"][0]["exercises"][0]["sets"]
    assert len(sets) == 3
    assert body["days"][0]["exercises"][0]["target_sets"] == 3
    assert sets[1]["weight_kg"] == 65

    _activate(alice, csrf, body["id"])
    occurrence = _schedule(alice, today, today)[0]
    record = _draft_occurrence(alice, csrf, occurrence["occurrence_id"])
    assert record["total_count"] == 3
    assert len(record["exercises"][0]["target"]["sets"]) == 3
    action_id = record["exercises"][0]["id"]

    first = alice.patch(
        f"/api/records/{record['id']}/actions/{action_id}",
        headers=_csrf(csrf),
        json={
            "expected_version": record["version"],
            "set_index": 1,
            "set_completed": True,
            "reps": 10,
            "weight_kg": 62.5,
        },
    )
    assert first.status_code == 200, first.text
    data = first.json()["data"]["record"]
    assert data["completed_count"] == 1
    assert data["total_count"] == 3
    assert data["exercises"][0]["completed"] is False
    assert data["exercises"][0]["target"]["sets"][0]["weight_kg"] == 62.5

    all_done = alice.patch(
        f"/api/records/{data['id']}/actions/{action_id}",
        headers=_csrf(csrf),
        json={"expected_version": data["version"], "completed": True},
    )
    assert all_done.status_code == 200, all_done.text
    full = all_done.json()["data"]["record"]
    assert full["completed_count"] == 3
    assert full["exercises"][0]["completed"] is True
    submit = _submit(alice, csrf, full)
    assert submit["completion_result"] == "FULL"
    assert submit["completed_count"] == 3
    stats = _overview(alice, today, today)
    assert stats["action_completion_rate"] == 100.0


def test_t16_t17_same_day_and_adhoc(client: TestClient) -> None:
    alice, csrf = _alice(client)
    today = today_business()
    catalog = _exercise_ids(alice)
    bench = catalog["杠铃卧推"]["id"]
    swim = catalog["游泳"]["id"]
    plan = _create_plan(
        alice, csrf, name="同日计划", start=today, days=[_day(today.isoweekday(), "基础", [bench])]
    )
    _activate(alice, csrf, plan["id"])
    before = _overview(alice, today, today)
    added = alice.put(
        f"/api/schedule/overrides/{today.isoformat()}",
        headers=_csrf(csrf),
        json={
            "mode": "ADD",
            "title": "追加",
            "exercises": [{"exercise_id": swim, "sort_order": 1, "target_duration_min": 20}],
        },
    )
    assert added.status_code == 200, added.text
    items = _schedule(alice, today, today)
    assert len(items) == 2
    for item in items:
        record = _draft_occurrence(alice, csrf, item["occurrence_id"])
        record = _set_completed(alice, csrf, record, {0})
        _submit(alice, csrf, record)
    adhoc = alice.post(
        "/api/records/drafts",
        headers=_csrf(csrf),
        json={
            "workout_date": today.isoformat(),
            "title": "自由有氧",
            "exercises": [{"exercise_id": swim, "sort_order": 1, "target_duration_min": 30}],
        },
    )
    assert adhoc.status_code == 201, adhoc.text
    adhoc_record = _set_completed(alice, csrf, adhoc.json()["data"], {0})
    _submit(alice, csrf, adhoc_record)
    stats = _overview(alice, today, today)
    assert stats["completed_sessions"] == 3
    assert stats["training_days"] == 1
    assert stats["planned_due"] == before["planned_due"] + 1


def test_t18_null_rates_without_plan(client: TestClient) -> None:
    alice, _csrf_token = _alice(client)
    today = today_business()
    stats = _overview(alice, today, today)
    assert stats["plan_completion_rate"] is None
    assert stats["action_completion_rate"] is None
    assert stats["planned_due"] == 0
    assert stats["completed_sessions"] == 0


def test_t26_version_conflict(client: TestClient) -> None:
    _init_admin(client)
    admin = _login(client, "admin", ADMIN_PASSWORD)
    created = client.post(
        "/api/admin/users",
        headers=_csrf(admin["csrf_token"]),
        json={"username": "alice", "display_name": "alice", "password": USER_PASSWORD},
    )
    assert created.status_code == 201, created.text
    device_a = _new_client()
    device_b = _new_client()
    login_a = _login(device_a, "alice", USER_PASSWORD)
    login_b = _login(device_b, "alice", USER_PASSWORD)
    today = today_business()
    bench = _exercise_ids(device_a)["杠铃卧推"]["id"]
    plan = _create_plan(
        device_a,
        login_a["csrf_token"],
        name="冲突计划",
        start=today,
        days=[_day(today.isoweekday(), "冲突", [bench])],
    )
    _activate(device_a, login_a["csrf_token"], plan["id"])
    occurrence = _schedule(device_a, today, today)[0]
    record = _draft_occurrence(device_a, login_a["csrf_token"], occurrence["occurrence_id"])
    action_id = record["exercises"][0]["id"]
    saved = device_b.patch(
        f"/api/records/{record['id']}/actions/{action_id}",
        headers=_csrf(login_b["csrf_token"]),
        json={"completed": True, "expected_version": record["version"]},
    )
    assert saved.status_code == 200, saved.text
    stale = device_a.patch(
        f"/api/records/{record['id']}/actions/{action_id}",
        headers=_csrf(login_a["csrf_token"]),
        json={"completed": False, "expected_version": record["version"]},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "VERSION_CONFLICT"
    current = device_a.get(f"/api/records/{record['id']}")
    assert current.json()["data"]["exercises"][0]["completed"] is True


def test_fixed_statistics_sample(client: TestClient) -> None:
    alice, csrf = _alice(client)
    today = today_business()
    d1 = today - timedelta(days=2)
    d2 = today - timedelta(days=1)
    d3 = today
    catalog = list(_exercise_ids(alice).values())
    strength = [item["id"] for item in catalog if item["category"] == "STRENGTH"][:4]
    cardio = next(item["id"] for item in catalog if item["category"] == "CARDIO")
    plan = _create_plan(
        alice,
        csrf,
        name="样例",
        start=d1,
        days=[
            _day(d1.isoweekday(), "P1", strength, 4),
            _day(d2.isoweekday(), "P2", strength, 4),
            _day(d3.isoweekday(), "P3", strength, 2),
        ],
    )
    _activate(alice, csrf, plan["id"])
    items = {item["workout_date"]: item for item in _schedule(alice, d1, d3)}
    assert set(items) == {d1.isoformat(), d2.isoformat(), d3.isoformat()}

    def submit_some(day, indexes: set[int]) -> None:
        record = _draft_occurrence(alice, csrf, items[day.isoformat()]["occurrence_id"])
        record = _set_completed(alice, csrf, record, indexes)
        _submit(alice, csrf, record)

    submit_some(d1, {0, 1, 2, 3})
    submit_some(d2, {0, 1})
    adhoc = alice.post(
        "/api/records/drafts",
        headers=_csrf(csrf),
        json={
            "workout_date": d1.isoformat(),
            "title": "额外有氧",
            "exercises": [
                {"exercise_id": cardio, "sort_order": index + 1, "target_duration_min": 15}
                for index in range(3)
            ],
        },
    )
    assert adhoc.status_code == 201, adhoc.text
    adhoc_record = _set_completed(alice, csrf, adhoc.json()["data"], {0, 1, 2})
    _submit(alice, csrf, adhoc_record)
    stats = _overview(alice, d1, d3)
    assert stats["planned_due"] == 3
    assert stats["planned_full"] == 1
    assert stats["plan_completion_rate"] == pytest.approx(33.33, abs=0.001)
    assert stats["action_completion_rate"] == pytest.approx(60, abs=0.001)
    assert stats["completed_sessions"] == 3
    assert stats["training_days"] == 2


def test_t20_t21_weight_rules(client: TestClient) -> None:
    alice, csrf = _alice(client)
    today = today_business()
    morning = datetime(today.year, today.month, today.day, 7, 30, tzinfo=TZ)
    evening = datetime(today.year, today.month, today.day, 21, 15, tzinfo=TZ)
    first = alice.post(
        "/api/weights",
        headers=_csrf(csrf),
        json={
            "record_date": today.isoformat(),
            "recorded_at": morning.isoformat(),
            "weight_kg": 70.5,
            "note": "晨起",
        },
    )
    assert first.status_code == 201, first.text
    second = alice.post(
        "/api/weights",
        headers=_csrf(csrf),
        json={
            "record_date": today.isoformat(),
            "recorded_at": evening.isoformat(),
            "weight_kg": 71.25,
            "note": "晚间",
        },
    )
    assert second.status_code == 201, second.text
    listed = alice.get("/api/weights", params={"from": today.isoformat(), "to": today.isoformat()})
    assert listed.status_code == 200
    assert len(listed.json()["data"]["items"]) == 2
    window_start = today - timedelta(days=2)
    summary = alice.get(
        "/api/statistics/weight",
        params={"from": window_start.isoformat(), "to": today.isoformat()},
    )
    assert summary.status_code == 200, summary.text
    body = summary.json()["data"]
    assert body["delta_kg"] is None
    assert body["delta_percent"] is None
    today_point = next(point for point in body["points"] if point["date"] == today.isoformat())
    assert today_point["weight_kg"] == pytest.approx(71.25)
    assert any(point["weight_kg"] is None for point in body["points"])
    assert all(point["weight_kg"] != 0 for point in body["points"])

    other = today - timedelta(days=1)
    earlier = datetime(other.year, other.month, other.day, 8, 0, tzinfo=TZ)
    third = alice.post(
        "/api/weights",
        headers=_csrf(csrf),
        json={
            "record_date": other.isoformat(),
            "recorded_at": earlier.isoformat(),
            "weight_kg": 70.0,
            "note": "",
        },
    )
    assert third.status_code == 201, third.text
    ranged = alice.get(
        "/api/statistics/weight",
        params={"from": other.isoformat(), "to": today.isoformat()},
    )
    delta = ranged.json()["data"]
    assert delta["delta_kg"] == pytest.approx(1.25)
    assert delta["latest"]["weight_kg"] == pytest.approx(71.25)


def test_t22_t25_sharing_and_rankings(client: TestClient) -> None:
    _init_admin(client)
    admin = _login(client, "admin", ADMIN_PASSWORD)
    alice = _bootstrap_user(client, admin["csrf_token"], "alice")
    bob = _bootstrap_user(client, admin["csrf_token"], "bob")
    cara = _bootstrap_user(client, admin["csrf_token"], "cara")
    dana = _bootstrap_user(client, admin["csrf_token"], "dana")
    sessions = {
        "alice": (alice, alice.get("/api/auth/me").json()["data"]),
        "bob": (bob, bob.get("/api/auth/me").json()["data"]),
        "cara": (cara, cara.get("/api/auth/me").json()["data"]),
        "dana": (dana, dana.get("/api/auth/me").json()["data"]),
    }

    def share(name: str, **flags: bool) -> None:
        user, me = sessions[name]
        payload = {
            "share_training_stats": False,
            "share_weight_change": False,
            "share_weight_values": False,
            **flags,
        }
        response = user.patch("/api/settings/sharing", headers=_csrf(me["csrf_token"]), json=payload)
        assert response.status_code == 200, response.text

    share("alice", share_weight_change=True)
    today = today_business()
    previous = today - timedelta(days=1)

    def add_weight(name: str, day, kg: float) -> None:
        user, me = sessions[name]
        moment = datetime(day.year, day.month, day.day, 9, 0, tzinfo=TZ)
        response = user.post(
            "/api/weights",
            headers=_csrf(me["csrf_token"]),
            json={
                "record_date": day.isoformat(),
                "recorded_at": moment.isoformat(),
                "weight_kg": kg,
                "note": "",
            },
        )
        assert response.status_code == 201, response.text

    add_weight("alice", previous, 70)
    add_weight("alice", today, 69)
    alice_id = sessions["alice"][1]["user"]["id"]
    bob_id = sessions["bob"][1]["user"]["id"]
    params = {
        "user_ids": f"{alice_id},{bob_id}",
        "metric": "weight_change",
        "from": previous.isoformat(),
        "to": today.isoformat(),
    }
    denied = bob.get("/api/comparison/weight-trends", params={"user_ids": params["user_ids"], "from": params["from"], "to": params["to"]})
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "SHARING_NOT_ALLOWED"
    allowed = bob.get("/api/comparison/metrics", params=params)
    assert allowed.status_code == 200, allowed.text
    assert allowed.headers["cache-control"] == "no-store"
    alice_metric = next(item for item in allowed.json()["data"]["items"] if item["user_id"] == alice_id)
    assert alice_metric["delta_kg"] == pytest.approx(-1)
    assert "weight_kg" not in alice_metric

    share("alice", share_weight_change=False)
    revoked = bob.get("/api/comparison/metrics", params=params)
    assert revoked.status_code == 403
    candidates = bob.get("/api/comparison/users", params={"scope": "weight_change"})
    ids = {item["id"] for item in candidates.json()["data"]["items"]}
    assert alice_id not in ids
    assert bob_id in ids

    share("alice", share_training_stats=True)
    share("bob", share_training_stats=True)
    share("cara", share_training_stats=True)
    share("dana", share_training_stats=True)
    bench = _exercise_ids(alice)["杠铃卧推"]["id"]

    def submit_sessions(name: str, count: int, full: bool) -> None:
        user, me = sessions[name]
        start = today - timedelta(days=6)
        plan = _create_plan(
            user,
            me["csrf_token"],
            name=f"{name}计划",
            start=start,
            days=[_day((start + timedelta(days=offset)).isoweekday(), "训练", [bench]) for offset in range(count)],
        )
        _activate(user, me["csrf_token"], plan["id"])
        items = _schedule(user, start, today)
        chosen = items[:count]
        assert len(chosen) >= count
        for item in chosen:
            record = _draft_occurrence(user, me["csrf_token"], item["occurrence_id"])
            if full:
                record = _set_completed(user, me["csrf_token"], record, set(range(len(record["exercises"]))))
                _submit(user, me["csrf_token"], record)
            elif item == chosen[0]:
                _submit(user, me["csrf_token"], record)

    submit_sessions("alice", 1, True)
    submit_sessions("bob", 1, True)
    submit_sessions("cara", 1, False)
    rankings = bob.get(
        "/api/comparison/rankings",
        params={"metric": "plan_rate", "from": (today - timedelta(days=6)).isoformat(), "to": today.isoformat()},
    )
    assert rankings.status_code == 200, rankings.text
    body = rankings.json()["data"]
    ranked = {item["display_name"]: item for item in body["items"]}
    assert ranked["alice"]["rank"] == 1
    assert ranked["bob"]["rank"] == 1
    assert ranked["cara"]["rank"] == 3
    assert "dana" not in ranked
    assert any(item["display_name"] == "dana" and item["label"] == "无数据" for item in body["unranked"])
    assert "exercises" not in rankings.text

    hidden = bob.get(f"/api/records/{1}")
    assert hidden.status_code == 404


def test_t28_backup_and_restore(client: TestClient) -> None:
    _init_admin(client)
    admin = _login(client, "admin", ADMIN_PASSWORD)
    csrf = admin["csrf_token"]
    today = today_business()
    moment = datetime(today.year, today.month, today.day, 8, 0, tzinfo=TZ)
    created = client.post(
        "/api/weights",
        headers=_csrf(csrf),
        json={
            "record_date": today.isoformat(),
            "recorded_at": moment.isoformat(),
            "weight_kg": 68.5,
            "note": "备份前",
        },
    )
    assert created.status_code == 201, created.text
    backup = client.post("/api/admin/backups", headers=_csrf(csrf))
    assert backup.status_code == 201, backup.text
    backup_id = backup.json()["data"]["filename"]
    extra = client.post(
        "/api/weights",
        headers=_csrf(csrf),
        json={
            "record_date": today.isoformat(),
            "recorded_at": datetime(today.year, today.month, today.day, 18, 0, tzinfo=TZ).isoformat(),
            "weight_kg": 80,
            "note": "备份后",
        },
    )
    assert extra.status_code == 201, extra.text
    restored = client.post(
        f"/api/admin/backups/{backup_id}/restore",
        headers=_csrf(csrf),
        json={"confirm": "RESTORE"},
    )
    assert restored.status_code == 200, restored.text
    listed = client.get("/api/weights")
    assert listed.status_code == 200, listed.text
    notes = [item["note"] for item in listed.json()["data"]["items"]]
    assert notes == ["备份前"]
    health = client.get("/api/admin/health")
    assert health.status_code == 200
    assert health.json()["data"]["last_backup_at"]


def test_migration_upgrade_and_downgrade(tmp_path: Path) -> None:
    backend = Path(__file__).resolve().parents[2]
    env = dict(**{key: value for key, value in __import__("os").environ.items()})
    env["APP_DATA_DIR"] = str(tmp_path)
    env["BACKUP_DIR"] = str(tmp_path / "backups")
    env["SCHEDULE_HORIZON_DAYS"] = "30"

    def run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "alembic", *args],
            cwd=backend,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    upgraded = run("upgrade", "head")
    assert upgraded.returncode == 0, upgraded.stderr
    downgraded = run("downgrade", "0002_t1_auth_exercises")
    assert downgraded.returncode == 0, downgraded.stderr
    again = run("upgrade", "head")
    assert again.returncode == 0, again.stderr

    import sqlite3

    connection = sqlite3.connect(tmp_path / "fitness.db")
    try:
        names = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        indexes = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='index'")
        }
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(plan_exercises)")
        }
    finally:
        connection.close()
    expected = {
        "fitness_plans",
        "plan_days",
        "plan_exercises",
        "plan_revisions",
        "date_overrides",
        "schedule_occurrences",
        "workout_sessions",
        "workout_exercises",
        "weight_records",
    }
    assert expected <= names
    assert "uq_active_weekly_plan_user" in indexes
    assert "sets_json" in columns
    assert "capacity" in columns
