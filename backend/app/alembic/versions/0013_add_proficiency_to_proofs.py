"""Add proficiency_level to proofs table

Revision ID: 0013_proficiency
Revises: 0012_kanban_share
Create Date: 2026-02-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_proficiency"
down_revision = "0012_kanban_share"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "proofs",
        sa.Column("proficiency_level", sa.String(32), nullable=True, server_default="intermediate"),
    )


def downgrade() -> None:
    op.drop_column("proofs", "proficiency_level")
