"""Add capacity to plan_exercises for free-text volume.

Revision ID: 0004_plan_exercise_capacity
Revises: 0003_t2_plans_workouts
Create Date: 2026-11-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_plan_exercise_capacity"
down_revision = "0003_t2_plans_workouts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("plan_exercises") as batch:
        batch.add_column(sa.Column("capacity", sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("plan_exercises") as batch:
        batch.drop_column("capacity")
