"""eval definitions

Revision ID: f9c2e7a1b4d6
Revises: 6e2665bdee8f
Create Date: 2026-08-17 10:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f9c2e7a1b4d6"
down_revision: str | None = "6e2665bdee8f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "eval_definitions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("schema_name", sa.String(length=64), nullable=False),
        sa.Column("cases", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_eval_definitions_slug", "eval_definitions", ["slug"])
    op.add_column("eval_runs", sa.Column("definition_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_eval_runs_definition_id",
        "eval_runs",
        "eval_definitions",
        ["definition_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_eval_runs_definition_id", "eval_runs", type_="foreignkey")
    op.drop_column("eval_runs", "definition_id")
    op.drop_index("ix_eval_definitions_slug", table_name="eval_definitions")
    op.drop_table("eval_definitions")
