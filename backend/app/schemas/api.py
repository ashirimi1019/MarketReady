from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Any, List, Optional


class MajorOut(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None


class PathwayOut(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None


class PathwayWithCompatibility(PathwayOut):
    is_compatible: bool
    notes: Optional[str] = None


class AuthRegisterIn(BaseModel):
    username: str
    email: Optional[str] = None
    password: str


class AuthLoginIn(BaseModel):
    username: str
    password: str


class AuthOut(BaseModel):
    user_id: str
    auth_token: Optional[str] = None
    refresh_token: Optional[str] = None
    access_expires_at: Optional[datetime] = None
    refresh_expires_at: Optional[datetime] = None
    email_verification_required: bool = False
    message: Optional[str] = None
    dev_code: Optional[str] = None


class AuthVerifyEmailIn(BaseModel):
    username: str
    code: str


class AuthResendVerificationIn(BaseModel):
    username: str


class AuthPasswordForgotIn(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None


class AuthPasswordResetIn(BaseModel):
    username: str
    code: str
    new_password: str


class AuthRefreshIn(BaseModel):
    refresh_token: str


class AuthLogoutIn(BaseModel):
    refresh_token: str


class AuthActionOut(BaseModel):
    ok: bool
    message: str
    dev_code: Optional[str] = None


class SelectPathwayIn(BaseModel):
    major_id: UUID
    pathway_id: UUID
    cohort: Optional[str] = None
    cohort_id: Optional[UUID] = None


class UserPathwayOut(BaseModel):
    major_id: UUID
    pathway_id: UUID
    cohort: Optional[str] = None
    cohort_id: Optional[UUID] = None
    checklist_version_id: Optional[UUID] = None
    selected_at: datetime


class StudentProfileIn(BaseModel):
    semester: Optional[str] = None
    state: Optional[str] = None
    university: Optional[str] = None
    masters_interest: Optional[bool] = None
    masters_target: Optional[str] = None
    masters_timeline: Optional[str] = None
    masters_status: Optional[str] = None


class StudentProfileOut(BaseModel):
    id: UUID
    user_id: str
    semester: Optional[str] = None
    state: Optional[str] = None
    university: Optional[str] = None
    masters_interest: bool = False
    masters_target: Optional[str] = None
    masters_timeline: Optional[str] = None
    masters_status: Optional[str] = None
    resume_url: Optional[str] = None
    resume_view_url: Optional[str] = None
    resume_filename: Optional[str] = None
    resume_uploaded_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class ChecklistItemOut(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    tier: str
    rationale: Optional[str] = None
    is_critical: bool
    allowed_proof_types: List[str]
    status: str


class PresignIn(BaseModel):
    filename: str
    content_type: str


class PresignOut(BaseModel):
    upload_url: str
    file_url: str
    key: Optional[str] = None


class ProofIn(BaseModel):
    checklist_item_id: UUID
    proof_type: str
    url: str
    metadata: Optional[dict[str, Any]] = None


class ProofOut(BaseModel):
    id: UUID
    checklist_item_id: UUID
    proof_type: str
    url: str
    view_url: Optional[str] = None
    status: str
    review_note: Optional[str] = None
    created_at: datetime


class ReadinessOut(BaseModel):
    score: float
    band: str
    capped: bool
    cap_reason: Optional[str] = None
    top_gaps: List[str]
    next_actions: List[str]


class TimelineOut(BaseModel):
    milestone_id: UUID
    title: str
    description: Optional[str] = None
    semester_index: int


class AiGuideIn(BaseModel):
    question: Optional[str] = None


class AiGuideOut(BaseModel):
    explanation: str
    decision: Optional[str] = None
    recommendations: List[str] = Field(default_factory=list)
    recommended_certificates: List[str] = Field(default_factory=list)
    materials_to_master: List[str] = Field(default_factory=list)
    market_top_skills: List[str] = Field(default_factory=list)
    market_alignment: List[str] = Field(default_factory=list)
    priority_focus_areas: List[str] = Field(default_factory=list)
    weekly_plan: List[str] = Field(default_factory=list)
    evidence_snippets: List[str] = Field(default_factory=list)
    confidence_by_item: dict[str, float] = Field(default_factory=dict)
    next_actions: List[str]
    suggested_proof_types: List[str]
    cited_checklist_item_ids: List[UUID]
    resume_detected: bool = False
    resume_strengths: List[str] = Field(default_factory=list)
    resume_improvements: List[str] = Field(default_factory=list)
    uncertainty: Optional[str] = None


class AiEvidenceMapOut(BaseModel):
    matched_count: int
    mode: str
    matched_item_ids: List[UUID] = Field(default_factory=list)


class AiGuideFeedbackIn(BaseModel):
    helpful: bool
    comment: Optional[str] = None
    context_item_ids: List[UUID] = Field(default_factory=list)


class AiGuideFeedbackOut(BaseModel):
    ok: bool
    message: str


class AdminAiSummaryIn(BaseModel):
    source_text: str
    purpose: Optional[str] = None


class AdminAiSummaryOut(BaseModel):
    summary: str
    rationale_draft: Optional[str] = None


class AdminPathwayIn(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True


class AdminPathwayOut(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    is_active: bool


class AdminSkillIn(BaseModel):
    name: str
    description: Optional[str] = None


class AdminSkillOut(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None


class AdminSkillUpdateIn(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class AdminChecklistItemIn(BaseModel):
    title: str
    description: Optional[str] = None
    tier: str
    rationale: Optional[str] = None
    is_critical: bool = False
    allowed_proof_types: List[str] = Field(default_factory=list)
    skill_id: Optional[UUID] = None
    skill_name: Optional[str] = None


class AdminChecklistDraftIn(BaseModel):
    items: List[AdminChecklistItemIn] = Field(default_factory=list)


class AdminChecklistDraftOut(BaseModel):
    version_id: UUID
    version_number: int
    status: str
    item_count: int


class AdminChecklistVersionOut(BaseModel):
    id: UUID
    pathway_id: UUID
    version_number: int
    status: str
    published_at: Optional[datetime] = None
    item_count: int


class AdminChecklistItemOut(BaseModel):
    id: UUID
    version_id: UUID
    skill_id: Optional[UUID] = None
    title: str
    description: Optional[str] = None
    tier: str
    rationale: Optional[str] = None
    is_critical: bool
    allowed_proof_types: List[str]


class AdminChecklistItemUpdateIn(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    tier: Optional[str] = None
    rationale: Optional[str] = None
    is_critical: Optional[bool] = None
    allowed_proof_types: Optional[List[str]] = None
    skill_id: Optional[UUID] = None


class AdminPublishOut(BaseModel):
    version_id: UUID
    status: str
    published_at: datetime


class AdminMilestoneIn(BaseModel):
    pathway_id: UUID
    title: str
    description: Optional[str] = None
    semester_index: int


class AdminMilestoneOut(BaseModel):
    milestone_id: UUID
    pathway_id: UUID
    title: str
    description: Optional[str] = None
    semester_index: int


class AdminProofVerifyIn(BaseModel):
    status: str = "verified"


class AdminProofVerifyOut(BaseModel):
    id: UUID
    status: str


class AdminProofOut(BaseModel):
    id: UUID
    user_id: str
    checklist_item_id: UUID
    proof_type: str
    url: str
    view_url: Optional[str] = None
    status: str
    review_note: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    created_at: datetime


class AdminProofUpdateIn(BaseModel):
    status: Optional[str] = None
    url: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    review_note: Optional[str] = None


class MarketIngestIn(BaseModel):
    source: str
    storage_key: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class MarketIngestOut(BaseModel):
    id: UUID
    source: str
    fetched_at: datetime
    storage_key: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class MarketExternalIngestIn(BaseModel):
    provider: str
    pathway_id: Optional[UUID] = None
    query: Optional[str] = None
    role_family: Optional[str] = None
    limit: int = 25


class MarketExternalIngestOut(BaseModel):
    provider: str
    ingested: int
    created_signals: int


class MarketSignalIn(BaseModel):
    pathway_id: Optional[UUID] = None
    skill_id: Optional[UUID] = None
    skill_name: Optional[str] = None
    role_family: Optional[str] = None
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    frequency: Optional[float] = None
    source_count: Optional[int] = None
    metadata: Optional[dict[str, Any]] = None


class MarketSignalsIn(BaseModel):
    signals: List[MarketSignalIn] = Field(default_factory=list)


class MarketSignalsOut(BaseModel):
    created: int


class MarketSignalOut(BaseModel):
    id: UUID
    pathway_id: Optional[UUID] = None
    skill_id: Optional[UUID] = None
    skill_name: Optional[str] = None
    role_family: Optional[str] = None
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    frequency: Optional[float] = None
    source_count: Optional[int] = None
    metadata: Optional[dict[str, Any]] = None


class MarketProposalIn(BaseModel):
    pathway_id: UUID
    summary: Optional[str] = None
    diff: Optional[dict[str, Any]] = None
    proposed_version_number: Optional[int] = None


class MarketCopilotProposalIn(BaseModel):
    pathway_id: UUID
    signal_ids: List[UUID] = Field(default_factory=list)
    instruction: Optional[str] = None


class MarketProposalOut(BaseModel):
    id: UUID
    pathway_id: UUID
    proposed_version_number: Optional[int] = None
    status: str
    summary: Optional[str] = None
    diff: Optional[dict[str, Any]] = None
    created_at: datetime
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    published_at: Optional[datetime] = None
    published_by: Optional[str] = None


class ChecklistChangeLogOut(BaseModel):
    id: UUID
    pathway_id: UUID
    from_version_id: Optional[UUID] = None
    to_version_id: Optional[UUID] = None
    change_type: str
    summary: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    created_by: Optional[str] = None
    created_at: datetime


class StudentGoalIn(BaseModel):
    title: str
    description: Optional[str] = None
    target_date: Optional[datetime] = None


class StudentGoalUpdateIn(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    target_date: Optional[datetime] = None


class StudentGoalOut(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    status: str
    target_date: Optional[datetime] = None
    last_check_in_at: Optional[datetime] = None
    streak_days: int
    created_at: datetime
    updated_at: datetime


class StudentGoalCheckInOut(BaseModel):
    id: UUID
    streak_days: int
    last_check_in_at: datetime


class StudentNotificationOut(BaseModel):
    id: UUID
    kind: str
    message: str
    is_read: bool
    metadata: Optional[dict[str, Any]] = None
    created_at: datetime


class StudentEngagementSummaryOut(BaseModel):
    goals_total: int
    goals_completed: int
    active_streak_days: int
    unread_notifications: int
    next_deadlines: List[str] = Field(default_factory=list)
