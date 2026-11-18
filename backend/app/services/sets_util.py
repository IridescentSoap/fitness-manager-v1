"""Structured per-set helpers for plans and workout drafts."""

from __future__ import annotations

import json
from typing import Any

from app.core.errors import AppError


def _num(value: object, label: str) -> float | int | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise AppError(422, "VALIDATION_ERROR", f"{label}无效") from exc
    if number < 0:
        raise AppError(422, "VALIDATION_ERROR", f"{label}不能为负")
    if float(number).is_integer():
        return int(number)
    return round(number, 2)


def normalize_set(
    raw: dict[str, Any],
    *,
    set_index: int,
    with_completed: bool = False,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "set_index": set_index,
        "reps": _num(raw.get("reps"), "次数"),
        "weight_kg": _num(raw.get("weight_kg"), "重量"),
        "duration_min": _num(raw.get("duration_min"), "时长"),
        "distance_km": _num(raw.get("distance_km"), "距离"),
    }
    if with_completed:
        item["completed"] = bool(raw.get("completed"))
        item["completed_at"] = raw.get("completed_at")
    return item


def sets_from_legacy(ex: dict[str, Any], *, with_completed: bool = False) -> list[dict[str, Any]]:
    count = int(ex.get("target_sets") or 1)
    if count < 1:
        count = 1
    template = {
        "reps": ex.get("target_reps"),
        "weight_kg": ex.get("target_weight_kg"),
        "duration_min": ex.get("target_duration_min"),
        "distance_km": ex.get("target_distance_km"),
    }
    return [
        normalize_set(template, set_index=index, with_completed=with_completed)
        for index in range(1, count + 1)
    ]


def normalize_sets(
    raw_sets: object | None,
    *,
    with_completed: bool = False,
) -> list[dict[str, Any]]:
    if not isinstance(raw_sets, list) or not raw_sets:
        raise AppError(422, "VALIDATION_ERROR", "每个动作至少包含 1 组")
    if len(raw_sets) > 50:
        raise AppError(422, "VALIDATION_ERROR", "单个动作最多 50 组")
    out: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_sets, start=1):
        if not isinstance(raw, dict):
            raise AppError(422, "VALIDATION_ERROR", "组数据无效")
        out.append(normalize_set(raw, set_index=index, with_completed=with_completed))
    return out


def resolve_sets(ex: dict[str, Any], *, with_completed: bool = False) -> list[dict[str, Any]]:
    if isinstance(ex.get("sets"), list) and ex["sets"]:
        return normalize_sets(ex["sets"], with_completed=with_completed)
    return sets_from_legacy(ex, with_completed=with_completed)


def summarize_sets(sets: list[dict[str, Any]]) -> dict[str, Any]:
    first = sets[0] if sets else {}
    return {
        "target_sets": len(sets) if sets else None,
        "target_reps": first.get("reps"),
        "target_weight_kg": first.get("weight_kg"),
        "target_duration_min": first.get("duration_min"),
        "target_distance_km": first.get("distance_km"),
    }


def sets_json_dumps(sets: list[dict[str, Any]]) -> str:
    # Persist plan sets without completion flags.
    payload = [
        {
            "set_index": item["set_index"],
            "reps": item.get("reps"),
            "weight_kg": item.get("weight_kg"),
            "duration_min": item.get("duration_min"),
            "distance_km": item.get("distance_km"),
        }
        for item in sets
    ]
    return json.dumps(payload, ensure_ascii=False)


def parse_sets_json(raw: str | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return data


def validate_sets_for_category(category: str, sets: list[dict[str, Any]]) -> None:
    if not sets:
        raise AppError(422, "VALIDATION_ERROR", "每个动作至少包含 1 组")
    for item in sets:
        if category == "STRENGTH":
            if item.get("reps") is None and item.get("weight_kg") is None:
                raise AppError(422, "VALIDATION_ERROR", "力量组需要次数或重量")
        elif category == "CARDIO":
            if item.get("duration_min") is None and item.get("distance_km") is None:
                raise AppError(422, "VALIDATION_ERROR", "有氧组需要时长或距离")
        elif category == "STRETCH":
            if item.get("duration_min") is None:
                raise AppError(422, "VALIDATION_ERROR", "拉伸组需要时长")


def set_count_of_target(target: dict[str, Any]) -> int:
    sets = target.get("sets")
    if isinstance(sets, list) and sets:
        return len(sets)
    n = target.get("target_sets")
    if n is not None:
        try:
            return max(1, int(n))
        except (TypeError, ValueError):
            return 1
    return 1


def completed_set_count(target: dict[str, Any], *, exercise_completed: bool) -> int:
    sets = target.get("sets")
    if isinstance(sets, list) and sets:
        return sum(1 for item in sets if item.get("completed"))
    if exercise_completed:
        return set_count_of_target(target)
    return 0


def all_sets_completed(sets: list[dict[str, Any]]) -> bool:
    return bool(sets) and all(bool(item.get("completed")) for item in sets)


def apply_all_sets_completed(
    sets: list[dict[str, Any]],
    completed: bool,
    completed_at: str | None,
) -> list[dict[str, Any]]:
    out = []
    for item in sets:
        row = dict(item)
        row["completed"] = completed
        row["completed_at"] = completed_at if completed else None
        out.append(row)
    return out


def snapshot_set_total(snapshot_item: dict[str, Any]) -> int:
    return set_count_of_target(snapshot_item)
