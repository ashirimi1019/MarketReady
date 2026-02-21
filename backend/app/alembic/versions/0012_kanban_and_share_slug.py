"""add kanban_tasks table and share_slug to student_profiles

Revision ID: 0012
Revises: 0011
Create Date: 2026-02-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0012_kanban_share"
down_revision = "0011_profile_github"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "student_profiles",
        sa.Column("share_slug", sa.String(120), nullable=True),
    )
    op.create_unique_constraint("uq_student_profiles_share_slug", "student_profiles", ["share_slug"])
    op.create_index("ix_student_profiles_share_slug", "student_profiles", ["share_slug"])

    op.create_table(
        "kanban_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(120), nullable=False, index=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="todo"),
        sa.Column("week_number", sa.Integer, nullable=True),
        sa.Column("skill_tag", sa.String(120), nullable=True),
        sa.Column("priority", sa.String(32), nullable=True, server_default="medium"),
        sa.Column("github_synced", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("ai_generated", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("kanban_tasks")
    op.drop_index("ix_student_profiles_share_slug", "student_profiles")
    op.drop_constraint("uq_student_profiles_share_slug", "student_profiles")
    op.drop_column("student_profiles", "share_slug")
