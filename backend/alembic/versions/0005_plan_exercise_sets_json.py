"""Add sets_json to plan_exercises and backfill from legacy targets.

Revision ID: 0005_plan_exercise_sets_json
Revises: 0004_plan_exercise_capacity
Create Date: 2026-11-16
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "0005_plan_exercise_sets_json"
down_revision = "0004_plan_exercise_capacity"
branch_labels = None
depends_on = None


def _legacy_sets(row: dict) -> list[dict]:
    count = int(row["target_sets"] or 1)
    if count < 1:
        count = 1
    template = {
        "reps": row["target_reps"],
        "weight_kg": float(row["target_weight_kg"]) if row["target_weight_kg"] is not None else None,
        "duration_min": row["target_duration_min"],
        "distance_km": float(row["target_distance_km"])
        if row["target_distance_km"] is not None
        else None,
    }
    return [
        {
            "set_index": index,
            "reps": template["reps"],
            "weight_kg": template["weight_kg"],
            "duration_min": template["duration_min"],
            "distance_km": template["distance_km"],
        }
        for index in range(1, count + 1)
    ]


def upgrade() -> None:
    with op.batch_alter_table("plan_exercises") as batch:
        batch.add_column(sa.Column("sets_json", sa.Text(), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            """
            SELECT id, target_sets, target_reps, target_weight_kg,
                   target_duration_min, target_distance_km, sets_json
            FROM plan_exercises
            """
        )
    ).mappings()
    for row in rows:
        if row["sets_json"]:
            continue
        payload = json.dumps(_legacy_sets(dict(row)), ensure_ascii=False)
        conn.execute(
            sa.text("UPDATE plan_exercises SET sets_json = :payload WHERE id = :id"),
            {"payload": payload, "id": row["id"]},
        )


def downgrade() -> None:
    with op.batch_alter_table("plan_exercises") as batch:
        batch.drop_column("sets_json")
