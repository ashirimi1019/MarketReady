"""Add AI interview simulator and resume architect tables

Revision ID: 0010_ai_interview_resume
Revises: 0009_auth_security_gov
Create Date: 2026-02-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0010_ai_interview_resume"
down_revision = "0009_auth_security_gov"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_interview_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(length=120), nullable=False),
        sa.Column("target_role", sa.String(length=160), nullable=True),
        sa.Column("job_description", sa.Text(), nullable=True),
        sa.Column("question_count", sa.Integer(), nullable=False, server_default=sa.text("5")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'active'")),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_ai_interview_sessions_user_id",
        "ai_interview_sessions",
        ["user_id"],
        unique=False,
    )
    op.alter_column("ai_interview_sessions", "question_count", server_default=None)
    op.alter_column("ai_interview_sessions", "status", server_default=None)

    op.create_table(
        "ai_interview_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("focus_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("focus_milestone_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_proof_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("difficulty", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["ai_interview_sessions.id"]),
        sa.ForeignKeyConstraint(["focus_item_id"], ["checklist_items.id"]),
        sa.ForeignKeyConstraint(["focus_milestone_id"], ["milestones.id"]),
        sa.ForeignKeyConstraint(["source_proof_id"], ["proofs.id"]),
    )
    op.create_index(
        "ix_ai_interview_questions_session_id",
        "ai_interview_questions",
        ["session_id"],
        unique=False,
    )

    op.create_table(
        "ai_interview_responses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("video_url", sa.Text(), nullable=True),
        sa.Column("ai_feedback", sa.Text(), nullable=True),
        sa.Column("ai_score", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["ai_interview_sessions.id"]),
        sa.ForeignKeyConstraint(["question_id"], ["ai_interview_questions.id"]),
    )
    op.create_index(
        "ix_ai_interview_responses_session_id",
        "ai_interview_responses",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        "ix_ai_interview_responses_question_id",
        "ai_interview_responses",
        ["question_id"],
        unique=True,
    )

    op.create_table(
        "ai_resume_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(length=120), nullable=False),
        sa.Column("target_role", sa.String(length=160), nullable=True),
        sa.Column("job_description", sa.Text(), nullable=True),
        sa.Column("ats_keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("markdown_content", sa.Text(), nullable=False),
        sa.Column("structured", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_ai_resume_artifacts_user_id", "ai_resume_artifacts", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ai_resume_artifacts_user_id", table_name="ai_resume_artifacts")
    op.drop_table("ai_resume_artifacts")

    op.drop_index("ix_ai_interview_responses_question_id", table_name="ai_interview_responses")
    op.drop_index("ix_ai_interview_responses_session_id", table_name="ai_interview_responses")
    op.drop_table("ai_interview_responses")

    op.drop_index("ix_ai_interview_questions_session_id", table_name="ai_interview_questions")
    op.drop_table("ai_interview_questions")

    op.drop_index("ix_ai_interview_sessions_user_id", table_name="ai_interview_sessions")
    op.drop_table("ai_interview_sessions")
