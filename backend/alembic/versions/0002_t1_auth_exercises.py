"""T1 auth, settings, exercises.

Revision ID: 0002_t1_auth_exercises
Revises: 0001_t0_baseline
Create Date: 2026-11-16
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_t1_auth_exercises"
down_revision: Union[str, None] = "0001_t0_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("session_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("role IN ('ADMIN', 'USER')", name="ck_users_role"),
        sa.CheckConstraint("status IN ('ACTIVE', 'DISABLED')", name="ck_users_status"),
        sa.UniqueConstraint("username"),
    )

    op.create_table(
        "sessions_auth",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("session_version", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("csrf_token_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_sessions_auth_user_id", "sessions_auth", ["user_id"])

    op.create_table(
        "user_settings",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("target_weight_kg", sa.Numeric(5, 2), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint(
            "target_weight_kg IS NULL OR (target_weight_kg >= 20 AND target_weight_kg <= 400)",
            name="ck_user_settings_target_weight",
        ),
    )

    op.create_table(
        "comparison_settings",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("share_training_stats", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("share_weight_change", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("share_weight_values", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "exercises",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint(
            "category IN ('STRENGTH', 'CARDIO', 'STRETCH')",
            name="ck_exercises_category",
        ),
        sa.UniqueConstraint("owner_user_id", "name", name="uq_exercises_owner_name"),
    )
    op.create_index("ix_exercises_owner_user_id", "exercises", ["owner_user_id"])

    op.create_table(
        "system_kv",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value_json", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("detail_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("system_kv")
    op.drop_index("ix_exercises_owner_user_id", table_name="exercises")
    op.drop_table("exercises")
    op.drop_table("comparison_settings")
    op.drop_table("user_settings")
    op.drop_index("ix_sessions_auth_user_id", table_name="sessions_auth")
    op.drop_table("sessions_auth")
    op.drop_table("users")
