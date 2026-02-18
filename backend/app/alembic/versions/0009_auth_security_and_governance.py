"""Add auth security/session/audit and product governance tables

Revision ID: 0009_auth_security_gov
Revises: 0008_student_profile_resume
Create Date: 2026-02-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0009_auth_security_gov"
down_revision = "0008_student_profile_resume"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("student_accounts", sa.Column("email", sa.String(length=255), nullable=True))
    op.add_column(
        "student_accounts",
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "student_accounts",
        sa.Column("email_verification_code", sa.String(length=24), nullable=True),
    )
    op.add_column(
        "student_accounts",
        sa.Column("email_verification_expires_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "student_accounts",
        sa.Column("password_reset_code", sa.String(length=24), nullable=True),
    )
    op.add_column(
        "student_accounts",
        sa.Column("password_reset_expires_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_student_accounts_email", "student_accounts", ["email"], unique=True)
    op.alter_column("student_accounts", "email_verified", server_default=None)

    op.create_table(
        "auth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(length=120), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"], unique=False)
    op.create_index(
        "ix_auth_sessions_refresh_token_hash",
        "auth_sessions",
        ["refresh_token_hash"],
        unique=True,
    )

    op.create_table(
        "auth_audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(length=120), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_auth_audit_logs_user_id", "auth_audit_logs", ["user_id"], unique=False)
    op.create_index("ix_auth_audit_logs_action", "auth_audit_logs", ["action"], unique=False)

    op.add_column(
        "market_update_proposals",
        sa.Column("approved_by", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "market_update_proposals",
        sa.Column("published_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "market_update_proposals",
        sa.Column("published_by", sa.String(length=120), nullable=True),
    )

    op.create_table(
        "checklist_change_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("pathway_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("to_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("change_type", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_by", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_checklist_change_logs_pathway_id",
        "checklist_change_logs",
        ["pathway_id"],
        unique=False,
    )

    op.create_table(
        "student_goals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("target_date", sa.DateTime(), nullable=True),
        sa.Column("last_check_in_at", sa.DateTime(), nullable=True),
        sa.Column("streak_days", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_student_goals_user_id", "student_goals", ["user_id"], unique=False)
    op.alter_column("student_goals", "streak_days", server_default=None)

    op.create_table(
        "student_notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_student_notifications_user_id",
        "student_notifications",
        ["user_id"],
        unique=False,
    )
    op.alter_column("student_notifications", "is_read", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_student_notifications_user_id", table_name="student_notifications")
    op.drop_table("student_notifications")

    op.drop_index("ix_student_goals_user_id", table_name="student_goals")
    op.drop_table("student_goals")

    op.drop_index("ix_checklist_change_logs_pathway_id", table_name="checklist_change_logs")
    op.drop_table("checklist_change_logs")

    op.drop_column("market_update_proposals", "published_by")
    op.drop_column("market_update_proposals", "published_at")
    op.drop_column("market_update_proposals", "approved_by")

    op.drop_index("ix_auth_audit_logs_action", table_name="auth_audit_logs")
    op.drop_index("ix_auth_audit_logs_user_id", table_name="auth_audit_logs")
    op.drop_table("auth_audit_logs")

    op.drop_index("ix_auth_sessions_refresh_token_hash", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")

    op.drop_index("ix_student_accounts_email", table_name="student_accounts")
    op.drop_column("student_accounts", "password_reset_expires_at")
    op.drop_column("student_accounts", "password_reset_code")
    op.drop_column("student_accounts", "email_verification_expires_at")
    op.drop_column("student_accounts", "email_verification_code")
    op.drop_column("student_accounts", "email_verified")
    op.drop_column("student_accounts", "email")
