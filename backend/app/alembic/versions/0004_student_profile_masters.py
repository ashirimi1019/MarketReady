"""Add masters fields to student profiles

Revision ID: 0004_student_profile_masters
Revises: 0003_student_profiles
Create Date: 2026-02-09 00:45:00
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_student_profile_masters"
down_revision = "0003_student_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "student_profiles",
        sa.Column("masters_interest", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("student_profiles", sa.Column("masters_target", sa.String(length=160), nullable=True))
    op.add_column("student_profiles", sa.Column("masters_timeline", sa.String(length=120), nullable=True))
    op.add_column("student_profiles", sa.Column("masters_status", sa.String(length=80), nullable=True))


def downgrade() -> None:
    op.drop_column("student_profiles", "masters_status")
    op.drop_column("student_profiles", "masters_timeline")
    op.drop_column("student_profiles", "masters_target")
    op.drop_column("student_profiles", "masters_interest")
