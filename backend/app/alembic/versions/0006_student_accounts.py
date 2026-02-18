"""Add student accounts table

Revision ID: 0006_student_accounts
Revises: 0005_proof_review_note
Create Date: 2026-02-16 00:20:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_student_accounts"
down_revision = "0005_proof_review_note"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "student_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("username", sa.String(length=120), nullable=False, unique=True),
        sa.Column("password_salt", sa.String(length=200), nullable=False),
        sa.Column("password_hash", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_student_accounts_username", "student_accounts", ["username"])


def downgrade() -> None:
    op.drop_index("ix_student_accounts_username", table_name="student_accounts")
    op.drop_table("student_accounts")
