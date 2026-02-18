"""Add review note to proofs

Revision ID: 0005_proof_review_note
Revises: 0004_student_profile_masters
Create Date: 2026-02-09 01:05:00
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_proof_review_note"
down_revision = "0004_student_profile_masters"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("proofs", sa.Column("review_note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("proofs", "review_note")
