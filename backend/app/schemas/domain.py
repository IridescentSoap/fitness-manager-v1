from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class SetIn(BaseModel):
    reps: int | float | None = Field(default=None, ge=0)
    weight_kg: float | None = Field(default=None, ge=0)
    duration_min: int | float | None = Field(default=None, ge=0)
    distance_km: float | None = Field(default=None, ge=0)
    completed: bool | None = None
    completed_at: str | None = None


class ExerciseTargetIn(BaseModel):
    exercise_id: int
    sort_order: int = Field(ge=1)
    target_sets: int | None = Field(default=None, ge=0)
    target_reps: int | None = Field(default=None, ge=0)
    target_weight_kg: float | None = Field(default=None, ge=0)
    target_duration_min: int | None = Field(default=None, ge=0)
    target_distance_km: float | None = Field(default=None, ge=0)
    capacity: str | None = Field(default=None, max_length=64)
    sets: list[SetIn] | None = None
    note: str | None = ""


class PlanDayIn(BaseModel):
    weekday: int = Field(ge=1, le=7)
    title: str = Field(min_length=1, max_length=100)
    is_rest: bool = False
    exercises: list[ExerciseTargetIn] = Field(default_factory=list)


class PlanCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    start_date: date
    end_date: date | None = None
    days: list[PlanDayIn]


class PlanUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    start_date: date | None = None
    end_date: date | None = None
    days: list[PlanDayIn] | None = None


class OverrideRequest(BaseModel):
    mode: Literal["REPLACE", "ADD", "REST"]
    title: str | None = Field(default=None, max_length=100)
    exercises: list[ExerciseTargetIn] = Field(default_factory=list)


class DraftRequest(BaseModel):
    occurrence_id: int | None = None
    workout_date: date | None = None
    title: str | None = Field(default=None, max_length=100)
    exercises: list[ExerciseTargetIn] | None = None


class ActionPatchRequest(BaseModel):
    expected_version: int = Field(ge=1)
    completed: bool | None = None
    capacity: str | None = Field(default=None, max_length=64)
    exercise_id: int | None = None
    sets: list[SetIn] | None = None
    set_index: int | None = Field(default=None, ge=1)
    reps: int | float | None = Field(default=None, ge=0)
    weight_kg: float | None = Field(default=None, ge=0)
    duration_min: int | float | None = Field(default=None, ge=0)
    distance_km: float | None = Field(default=None, ge=0)
    set_completed: bool | None = None


class AppendExercisesRequest(BaseModel):
    expected_version: int = Field(ge=1)
    exercises: list[ExerciseTargetIn] = Field(min_length=1)


class VersionRequest(BaseModel):
    expected_version: int = Field(ge=1)


class WeightCreateRequest(BaseModel):
    record_date: date
    recorded_at: datetime
    weight_kg: float
    note: str | None = Field(default=None, max_length=200)


class WeightUpdateRequest(BaseModel):
    record_date: date | None = None
    recorded_at: datetime | None = None
    weight_kg: float | None = None
    note: str | None = Field(default=None, max_length=200)


class RestoreBackupRequest(BaseModel):
    confirm: str
