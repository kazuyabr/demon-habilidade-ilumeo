"""eval definition thresholds

Revision ID: b3d8a2c5f7e1
Revises: f9c2e7a1b4d6
Create Date: 2026-08-18 11:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3d8a2c5f7e1"
down_revision: str | None = "f9c2e7a1b4d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "eval_definitions",
        sa.Column("thresholds", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("eval_definitions", "thresholds")
