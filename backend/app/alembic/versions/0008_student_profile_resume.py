"""Add resume fields to student profiles

Revision ID: 0008_student_profile_resume
Revises: 0007_proof_status_length
Create Date: 2026-02-16
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_student_profile_resume"
down_revision = "0007_proof_status_length"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("student_profiles", sa.Column("resume_url", sa.Text(), nullable=True))
    op.add_column("student_profiles", sa.Column("resume_filename", sa.String(length=255), nullable=True))
    op.add_column("student_profiles", sa.Column("resume_uploaded_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("student_profiles", "resume_uploaded_at")
    op.drop_column("student_profiles", "resume_filename")
    op.drop_column("student_profiles", "resume_url")
