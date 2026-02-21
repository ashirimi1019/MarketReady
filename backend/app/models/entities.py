from enum import Enum
from uuid import uuid4
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, ForeignKey, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class ChecklistTier(str, Enum):
    non_negotiable = "non_negotiable"
    strong_signal = "strong_signal"
    optional = "optional"


class ChecklistVersionStatus(str, Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


class Major(Base):
    __tablename__ = "majors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(120), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)


class CareerPathway(Base):
    __tablename__ = "career_pathways"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(120), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)


class Cohort(Base):
    __tablename__ = "cohorts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(80), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)


class MajorPathwayMap(Base):
    __tablename__ = "major_pathway_map"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    major_id = Column(UUID(as_uuid=True), ForeignKey("majors.id"), nullable=False)
    pathway_id = Column(UUID(as_uuid=True), ForeignKey("career_pathways.id"), nullable=False)
    is_compatible = Column(Boolean, default=True, nullable=False)
    notes = Column(Text, nullable=True)

    major = relationship("Major")
    pathway = relationship("CareerPathway")


class Skill(Base):
    __tablename__ = "skills"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(160), unique=True, nullable=False)
    description = Column(Text, nullable=True)


class ChecklistVersion(Base):
    __tablename__ = "checklist_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    pathway_id = Column(UUID(as_uuid=True), ForeignKey("career_pathways.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False)
    published_at = Column(DateTime, nullable=True)

    pathway = relationship("CareerPathway")


class ChecklistItem(Base):
    __tablename__ = "checklist_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    version_id = Column(UUID(as_uuid=True), ForeignKey("checklist_versions.id"), nullable=False)
    skill_id = Column(UUID(as_uuid=True), ForeignKey("skills.id"), nullable=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    tier = Column(String(32), nullable=False)
    rationale = Column(Text, nullable=True)
    is_critical = Column(Boolean, default=False, nullable=False)
    allowed_proof_types = Column(JSONB, nullable=False, default=list)

    version = relationship("ChecklistVersion")
    skill = relationship("Skill")


class Milestone(Base):
    __tablename__ = "milestones"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    pathway_id = Column(UUID(as_uuid=True), ForeignKey("career_pathways.id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    semester_index = Column(Integer, nullable=False)

    pathway = relationship("CareerPathway")


class UserPathway(Base):
    __tablename__ = "user_pathways"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(String(120), nullable=False, index=True)
    major_id = Column(UUID(as_uuid=True), ForeignKey("majors.id"), nullable=False)
    pathway_id = Column(UUID(as_uuid=True), ForeignKey("career_pathways.id"), nullable=False)
    cohort = Column(String(80), nullable=True)
    cohort_id = Column(UUID(as_uuid=True), ForeignKey("cohorts.id"), nullable=True)
    checklist_version_id = Column(UUID(as_uuid=True), ForeignKey("checklist_versions.id"), nullable=True)
    selected_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    major = relationship("Major")
    pathway = relationship("CareerPathway")
    checklist_version = relationship("ChecklistVersion")
    cohort_ref = relationship("Cohort")


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(String(120), nullable=False, unique=True, index=True)
    semester = Column(String(80), nullable=True)
    state = Column(String(80), nullable=True)
    university = Column(String(160), nullable=True)
    masters_interest = Column(Boolean, default=False, nullable=False)
    masters_target = Column(String(160), nullable=True)
    masters_timeline = Column(String(120), nullable=True)
    masters_status = Column(String(80), nullable=True)
    github_username = Column(String(255), nullable=True)
    resume_url = Column(Text, nullable=True)
    resume_filename = Column(String(255), nullable=True)
    resume_uploaded_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class StudentAccount(Base):
    __tablename__ = "student_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    username = Column(String(120), nullable=False, unique=True, index=True)
    email = Column(String(255), nullable=True, unique=True, index=True)
    email_verified = Column(Boolean, default=False, nullable=False)
    email_verification_code = Column(String(24), nullable=True)
    email_verification_expires_at = Column(DateTime, nullable=True)
    password_reset_code = Column(String(24), nullable=True)
    password_reset_expires_at = Column(DateTime, nullable=True)
    password_salt = Column(String(200), nullable=False)
    password_hash = Column(String(200), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login_at = Column(DateTime, nullable=True)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(String(120), nullable=False, index=True)
    refresh_token_hash = Column(String(128), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(Text, nullable=True)


class AuthAuditLog(Base):
    __tablename__ = "auth_audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(String(120), nullable=True, index=True)
    action = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(Text, nullable=True)
    detail = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Proof(Base):
    __tablename__ = "proofs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(String(120), nullable=False, index=True)
    checklist_item_id = Column(UUID(as_uuid=True), ForeignKey("checklist_items.id"), nullable=False)
    proof_type = Column(String(80), nullable=False)
    url = Column(Text, nullable=False)
    status = Column(String(32), default="submitted", nullable=False)
    review_note = Column(Text, nullable=True)
    metadata_json = Column("metadata", JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    checklist_item = relationship("ChecklistItem")


class AiAuditLog(Base):
    __tablename__ = "ai_audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(String(120), nullable=True, index=True)
    feature = Column(String(80), nullable=False)
    prompt_input = Column(JSONB, nullable=True)
    context_ids = Column(JSONB, nullable=True)
    model = Column(String(120), nullable=True)
    output = Column(Text, nullable=True)
    feedback = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class MarketRawIngestion(Base):
    __tablename__ = "market_raw_ingestions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    source = Column(String(120), nullable=False)
    fetched_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    storage_key = Column(Text, nullable=True)
    metadata_json = Column("metadata", JSONB, nullable=True)


class MarketSignal(Base):
    __tablename__ = "market_signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    pathway_id = Column(UUID(as_uuid=True), ForeignKey("career_pathways.id"), nullable=True)
    skill_id = Column(UUID(as_uuid=True), ForeignKey("skills.id"), nullable=True)
    role_family = Column(String(120), nullable=True)
    window_start = Column(DateTime, nullable=True)
    window_end = Column(DateTime, nullable=True)
    frequency = Column(Float, nullable=True)
    source_count = Column(Integer, nullable=True)
    metadata_json = Column("metadata", JSONB, nullable=True)


class MarketUpdateProposal(Base):
    __tablename__ = "market_update_proposals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    pathway_id = Column(UUID(as_uuid=True), ForeignKey("career_pathways.id"), nullable=False)
    proposed_version_number = Column(Integer, nullable=True)
    status = Column(String(16), nullable=False, default="draft")
    summary = Column(Text, nullable=True)
    diff = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(String(120), nullable=True)
    published_at = Column(DateTime, nullable=True)
    published_by = Column(String(120), nullable=True)


class ChecklistChangeLog(Base):
    __tablename__ = "checklist_change_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    pathway_id = Column(UUID(as_uuid=True), ForeignKey("career_pathways.id"), nullable=False, index=True)
    from_version_id = Column(UUID(as_uuid=True), ForeignKey("checklist_versions.id"), nullable=True)
    to_version_id = Column(UUID(as_uuid=True), ForeignKey("checklist_versions.id"), nullable=True)
    change_type = Column(String(32), nullable=False)
    summary = Column(Text, nullable=True)
    metadata_json = Column("metadata", JSONB, nullable=True)
    created_by = Column(String(120), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class StudentGoal(Base):
    __tablename__ = "student_goals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(String(120), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="active")
    target_date = Column(DateTime, nullable=True)
    last_check_in_at = Column(DateTime, nullable=True)
    streak_days = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class StudentNotification(Base):
    __tablename__ = "student_notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(String(120), nullable=False, index=True)
    kind = Column(String(64), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, nullable=False, default=False)
    metadata_json = Column("metadata", JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AiInterviewSession(Base):
    __tablename__ = "ai_interview_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(String(120), nullable=False, index=True)
    target_role = Column(String(160), nullable=True)
    job_description = Column(Text, nullable=True)
    question_count = Column(Integer, nullable=False, default=5)
    status = Column(String(32), nullable=False, default="active")
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AiInterviewQuestion(Base):
    __tablename__ = "ai_interview_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ai_interview_sessions.id"),
        nullable=False,
        index=True,
    )
    order_index = Column(Integer, nullable=False)
    prompt = Column(Text, nullable=False)
    focus_item_id = Column(UUID(as_uuid=True), ForeignKey("checklist_items.id"), nullable=True)
    focus_milestone_id = Column(UUID(as_uuid=True), ForeignKey("milestones.id"), nullable=True)
    source_proof_id = Column(UUID(as_uuid=True), ForeignKey("proofs.id"), nullable=True)
    difficulty = Column(String(32), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    session = relationship("AiInterviewSession")
    focus_item = relationship("ChecklistItem")
    focus_milestone = relationship("Milestone")
    source_proof = relationship("Proof")


class AiInterviewResponse(Base):
    __tablename__ = "ai_interview_responses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ai_interview_sessions.id"),
        nullable=False,
        index=True,
    )
    question_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ai_interview_questions.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    answer_text = Column(Text, nullable=True)
    video_url = Column(Text, nullable=True)
    ai_feedback = Column(Text, nullable=True)
    ai_score = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    session = relationship("AiInterviewSession")
    question = relationship("AiInterviewQuestion")


class AiResumeArtifact(Base):
    __tablename__ = "ai_resume_artifacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(String(120), nullable=False, index=True)
    target_role = Column(String(160), nullable=True)
    job_description = Column(Text, nullable=True)
    ats_keywords = Column(JSONB, nullable=True)
    markdown_content = Column(Text, nullable=False)
    structured_json = Column("structured", JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class KanbanTask(Base):
    __tablename__ = "kanban_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(String(120), nullable=False, index=True)
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="todo")  # todo, in_progress, done
    week_number = Column(Integer, nullable=True)
    skill_tag = Column(String(120), nullable=True)
    priority = Column(String(32), nullable=True, default="medium")  # low, medium, high
    github_synced = Column(Boolean, nullable=False, default=False)
    ai_generated = Column(Boolean, nullable=False, default=False)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
