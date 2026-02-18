"""Add cohorts, AI audit logs, and market intelligence tables

Revision ID: 0002_future_tables
Revises: 0001_initial
Create Date: 2026-02-09 00:00:01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_future_tables"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cohorts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("starts_at", sa.DateTime(), nullable=True),
        sa.Column("ends_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    op.add_column(
        "user_pathways",
        sa.Column("cohort_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cohorts.id"), nullable=True),
    )

    op.create_table(
        "ai_audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(length=120), nullable=True),
        sa.Column("feature", sa.String(length=80), nullable=False),
        sa.Column("prompt_input", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("context_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("output", sa.Text(), nullable=True),
        sa.Column("feedback", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_ai_audit_logs_user_id", "ai_audit_logs", ["user_id"])

    op.create_table(
        "market_raw_ingestions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    op.create_table(
        "market_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("pathway_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("career_pathways.id"), nullable=True),
        sa.Column("skill_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("skills.id"), nullable=True),
        sa.Column("role_family", sa.String(length=120), nullable=True),
        sa.Column("window_start", sa.DateTime(), nullable=True),
        sa.Column("window_end", sa.DateTime(), nullable=True),
        sa.Column("frequency", sa.Float(), nullable=True),
        sa.Column("source_count", sa.Integer(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    op.create_table(
        "market_update_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("pathway_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("career_pathways.id"), nullable=False),
        sa.Column("proposed_version_number", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("diff", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("market_update_proposals")
    op.drop_table("market_signals")
    op.drop_table("market_raw_ingestions")

    op.drop_index("ix_ai_audit_logs_user_id", table_name="ai_audit_logs")
    op.drop_table("ai_audit_logs")

    op.drop_column("user_pathways", "cohort_id")
    op.drop_table("cohorts")
