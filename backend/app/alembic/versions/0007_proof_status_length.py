"""Increase proofs.status length

Revision ID: 0007_proof_status_length
Revises: 0006_student_accounts
Create Date: 2026-02-16
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_proof_status_length"
down_revision = "0006_student_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "proofs",
        "status",
        existing_type=sa.String(length=16),
        type_=sa.String(length=32),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "proofs",
        "status",
        existing_type=sa.String(length=32),
        type_=sa.String(length=16),
        existing_nullable=False,
    )
