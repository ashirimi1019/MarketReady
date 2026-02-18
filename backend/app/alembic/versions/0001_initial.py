"""Initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-02-09 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "majors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    op.create_table(
        "career_pathways",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    op.create_table(
        "skills",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
    )

    op.create_table(
        "checklist_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("pathway_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("career_pathways.id"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "checklist_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("checklist_versions.id"), nullable=False),
        sa.Column("skill_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("skills.id"), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tier", sa.String(length=32), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("is_critical", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("allowed_proof_types", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )

    op.create_table(
        "milestones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("pathway_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("career_pathways.id"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("semester_index", sa.Integer(), nullable=False),
    )

    op.create_table(
        "major_pathway_map",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("major_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("majors.id"), nullable=False),
        sa.Column("pathway_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("career_pathways.id"), nullable=False),
        sa.Column("is_compatible", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    op.create_table(
        "user_pathways",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(length=120), nullable=False),
        sa.Column("major_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("majors.id"), nullable=False),
        sa.Column("pathway_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("career_pathways.id"), nullable=False),
        sa.Column("cohort", sa.String(length=80), nullable=True),
        sa.Column("checklist_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("checklist_versions.id"), nullable=True),
        sa.Column("selected_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "proofs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(length=120), nullable=False),
        sa.Column("checklist_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("checklist_items.id"), nullable=False),
        sa.Column("proof_type", sa.String(length=80), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'submitted'")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_index("ix_user_pathways_user_id", "user_pathways", ["user_id"])
    op.create_index("ix_proofs_user_id", "proofs", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_proofs_user_id", table_name="proofs")
    op.drop_index("ix_user_pathways_user_id", table_name="user_pathways")

    op.drop_table("proofs")
    op.drop_table("user_pathways")
    op.drop_table("major_pathway_map")
    op.drop_table("milestones")
    op.drop_table("checklist_items")
    op.drop_table("checklist_versions")
    op.drop_table("skills")
    op.drop_table("career_pathways")
    op.drop_table("majors")
