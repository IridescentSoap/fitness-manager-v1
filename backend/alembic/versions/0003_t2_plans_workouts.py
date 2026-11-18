"""T2-T4 plans, schedule, workouts, weights.

Revision ID: 0003_t2_plans_workouts
Revises: 0002_t1_auth_exercises
Create Date: 2026-11-16
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_t2_plans_workouts"
down_revision: Union[str, None] = "0002_t1_auth_exercises"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fitness_plans",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("current_revision_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("status IN ('DRAFT', 'ACTIVE', 'INACTIVE')", name="ck_fitness_plans_status"),
    )
    op.create_index("ix_fitness_plans_user_id", "fitness_plans", ["user_id"])
    op.create_index(
        "uq_active_weekly_plan_user",
        "fitness_plans",
        ["user_id"],
        unique=True,
        sqlite_where=sa.text("status = 'ACTIVE'"),
    )

    op.create_table(
        "plan_days",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("fitness_plans.id"), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("is_rest", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("weekday >= 1 AND weekday <= 7", name="ck_plan_days_weekday"),
        sa.UniqueConstraint("plan_id", "weekday", name="uq_plan_days_weekday"),
    )

    op.create_table(
        "plan_exercises",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("plan_day_id", sa.Integer(), sa.ForeignKey("plan_days.id"), nullable=False),
        sa.Column("exercise_id", sa.Integer(), sa.ForeignKey("exercises.id"), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("target_sets", sa.Integer(), nullable=True),
        sa.Column("target_reps", sa.Integer(), nullable=True),
        sa.Column("target_weight_kg", sa.Numeric(6, 2), nullable=True),
        sa.Column("target_duration_min", sa.Integer(), nullable=True),
        sa.Column("target_distance_km", sa.Numeric(7, 2), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.UniqueConstraint("plan_day_id", "sort_order", name="uq_plan_exercises_sort"),
    )

    op.create_table(
        "plan_revisions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("fitness_plans.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_until", sa.Date(), nullable=True),
        sa.Column("weekly_snapshot_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_plan_revisions_plan_id", "plan_revisions", ["plan_id"])

    op.create_table(
        "date_overrides",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workout_date", sa.Date(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=True),
        sa.Column("snapshot_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("mode IN ('REPLACE', 'ADD', 'REST')", name="ck_date_overrides_mode"),
        sa.UniqueConstraint("user_id", "workout_date", name="uq_date_overrides_user_date"),
    )
    op.create_index("ix_date_overrides_user_id", "date_overrides", ["user_id"])

    op.create_table(
        "schedule_occurrences",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workout_date", sa.Date(), nullable=False),
        sa.Column("slot", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("revision_id", sa.Integer(), sa.ForeignKey("plan_revisions.id"), nullable=True),
        sa.Column("title_snapshot", sa.String(length=100), nullable=False),
        sa.Column("exercise_snapshot_json", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("slot IN ('BASE', 'EXTRA')", name="ck_occurrences_slot"),
        sa.CheckConstraint("source IN ('WEEKLY', 'OVERRIDE')", name="ck_occurrences_source"),
        sa.CheckConstraint("status IN ('PLANNED', 'CANCELLED')", name="ck_occurrences_status"),
        sa.UniqueConstraint("user_id", "workout_date", "slot", name="uq_occurrence_user_date_slot"),
    )
    op.create_index("ix_schedule_occurrences_user_id", "schedule_occurrences", ["user_id"])
    op.create_index("ix_schedule_occurrences_workout_date", "schedule_occurrences", ["workout_date"])

    op.create_table(
        "workout_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("occurrence_id", sa.Integer(), sa.ForeignKey("schedule_occurrences.id"), nullable=True),
        sa.Column("workout_date", sa.Date(), nullable=False),
        sa.Column("title_snapshot", sa.String(length=100), nullable=False),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("origin IN ('PLAN', 'AD_HOC')", name="ck_workout_sessions_origin"),
        sa.CheckConstraint("status IN ('DRAFT', 'SUBMITTED')", name="ck_workout_sessions_status"),
        sa.UniqueConstraint("occurrence_id", name="uq_workout_sessions_occurrence"),
    )
    op.create_index("ix_workout_sessions_user_id", "workout_sessions", ["user_id"])
    op.create_index("ix_workout_sessions_workout_date", "workout_sessions", ["workout_date"])

    op.create_table(
        "workout_exercises",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("workout_sessions.id"), nullable=False),
        sa.Column("exercise_id", sa.Integer(), sa.ForeignKey("exercises.id"), nullable=True),
        sa.Column("exercise_name_snapshot", sa.String(length=100), nullable=False),
        sa.Column("category_snapshot", sa.Text(), nullable=False),
        sa.Column("target_snapshot_json", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("session_id", "sort_order", name="uq_workout_exercises_sort"),
    )

    op.create_table(
        "weight_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("record_date", sa.Date(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("weight_kg", sa.Numeric(5, 2), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("weight_kg >= 20 AND weight_kg <= 400", name="ck_weight_records_range"),
    )
    op.create_index("ix_weight_records_user_id", "weight_records", ["user_id"])
    op.create_index("ix_weight_records_record_date", "weight_records", ["record_date"])
    op.create_index(
        "ix_weight_records_user_date_time",
        "weight_records",
        ["user_id", "record_date", "recorded_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_weight_records_user_date_time", table_name="weight_records")
    op.drop_index("ix_weight_records_record_date", table_name="weight_records")
    op.drop_index("ix_weight_records_user_id", table_name="weight_records")
    op.drop_table("weight_records")
    op.drop_table("workout_exercises")
    op.drop_index("ix_workout_sessions_workout_date", table_name="workout_sessions")
    op.drop_index("ix_workout_sessions_user_id", table_name="workout_sessions")
    op.drop_table("workout_sessions")
    op.drop_index("ix_schedule_occurrences_workout_date", table_name="schedule_occurrences")
    op.drop_index("ix_schedule_occurrences_user_id", table_name="schedule_occurrences")
    op.drop_table("schedule_occurrences")
    op.drop_index("ix_date_overrides_user_id", table_name="date_overrides")
    op.drop_table("date_overrides")
    op.drop_index("ix_plan_revisions_plan_id", table_name="plan_revisions")
    op.drop_table("plan_revisions")
    op.drop_table("plan_exercises")
    op.drop_table("plan_days")
    op.drop_index("uq_active_weekly_plan_user", table_name="fitness_plans")
    op.drop_index("ix_fitness_plans_user_id", table_name="fitness_plans")
    op.drop_table("fitness_plans")
