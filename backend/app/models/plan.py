from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class FitnessPlan(Base):
    __tablename__ = "fitness_plans"
    __table_args__ = (
        Index(
            "uq_active_weekly_plan_user",
            "user_id",
            unique=True,
            sqlite_where=text("status = 'ACTIVE'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="DRAFT")
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    current_revision_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    days: Mapped[list[PlanDay]] = relationship(back_populates="plan", cascade="all, delete-orphan")
    revisions: Mapped[list[PlanRevision]] = relationship(back_populates="plan")


class PlanDay(Base):
    __tablename__ = "plan_days"
    __table_args__ = (UniqueConstraint("plan_id", "weekday", name="uq_plan_days_weekday"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("fitness_plans.id"), nullable=False)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    is_rest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    plan: Mapped[FitnessPlan] = relationship(back_populates="days")
    exercises: Mapped[list[PlanExercise]] = relationship(
        back_populates="plan_day", cascade="all, delete-orphan"
    )


class PlanExercise(Base):
    __tablename__ = "plan_exercises"
    __table_args__ = (UniqueConstraint("plan_day_id", "sort_order", name="uq_plan_exercises_sort"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_day_id: Mapped[int] = mapped_column(ForeignKey("plan_days.id"), nullable=False)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id"), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    target_sets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_reps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_weight_kg: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    target_duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_distance_km: Mapped[float | None] = mapped_column(Numeric(7, 2), nullable=True)
    capacity: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sets_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    plan_day: Mapped[PlanDay] = relationship(back_populates="exercises")


class PlanRevision(Base):
    __tablename__ = "plan_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("fitness_plans.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    weekly_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    plan: Mapped[FitnessPlan] = relationship(back_populates="revisions")


class DateOverride(Base):
    __tablename__ = "date_overrides"
    __table_args__ = (UniqueConstraint("user_id", "workout_date", name="uq_date_overrides_user_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    workout_date: Mapped[date] = mapped_column(Date, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ScheduleOccurrence(Base):
    __tablename__ = "schedule_occurrences"
    __table_args__ = (
        UniqueConstraint("user_id", "workout_date", "slot", name="uq_occurrence_user_date_slot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    workout_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    slot: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    revision_id: Mapped[int | None] = mapped_column(ForeignKey("plan_revisions.id"), nullable=True)
    title_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    exercise_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="PLANNED")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
