"""Add github_username to student profiles

Revision ID: 0011_profile_github
Revises: 0010_ai_interview_resume
Create Date: 2026-02-20
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_profile_github"
down_revision = "0010_ai_interview_resume"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns(table_name)}
    return column_name in columns


def upgrade() -> None:
    if not _has_column("student_profiles", "github_username"):
        op.add_column(
            "student_profiles",
            sa.Column("github_username", sa.String(length=255), nullable=True),
        )


def downgrade() -> None:
    if _has_column("student_profiles", "github_username"):
        op.drop_column("student_profiles", "github_username")
