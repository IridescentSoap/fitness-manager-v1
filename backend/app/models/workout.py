from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class WorkoutSession(Base):
    __tablename__ = "workout_sessions"
    __table_args__ = (UniqueConstraint("occurrence_id", name="uq_workout_sessions_occurrence"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    occurrence_id: Mapped[int | None] = mapped_column(
        ForeignKey("schedule_occurrences.id"), nullable=True
    )
    workout_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    title_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    origin: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="DRAFT")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    exercises: Mapped[list[WorkoutExercise]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class WorkoutExercise(Base):
    __tablename__ = "workout_exercises"
    __table_args__ = (UniqueConstraint("session_id", "sort_order", name="uq_workout_exercises_sort"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("workout_sessions.id"), nullable=False)
    exercise_id: Mapped[int | None] = mapped_column(ForeignKey("exercises.id"), nullable=True)
    exercise_name_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    category_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    target_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    session: Mapped[WorkoutSession] = relationship(back_populates="exercises")
