"""T0 baseline — empty schema placeholder.

Revision ID: 0001_t0_baseline
Revises:
Create Date: 2026-11-16

Domain tables are introduced starting in T1.
"""

from typing import Sequence, Union

revision: str = "0001_t0_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Intentionally empty: T0 only establishes Alembic wiring.
    pass


def downgrade() -> None:
    pass
