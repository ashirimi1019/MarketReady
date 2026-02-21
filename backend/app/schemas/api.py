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
    github_username: Optional[str] = None


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
    github_username: Optional[str] = None
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
    metadata: Optional[dict[str, Any]] = None
    created_at: datetime


class ReadinessOut(BaseModel):
    score: float
    checklist_score: Optional[float] = None
    engineering_score: Optional[float] = None
    market_alignment_score: Optional[float] = None
    band: str
    capped: bool
    cap_reason: Optional[str] = None
    top_gaps: List[str]
    next_actions: List[str]


class ReadinessRankOut(BaseModel):
    score: float
    band: str
    percentile: float
    rank: int
    total_students: int
    linkedin_share_text: str
    linkedin_share_url: str


class WeeklyStreakWeekOut(BaseModel):
    week_start: datetime
    week_label: str
    has_activity: bool


class WeeklyMilestoneStreakOut(BaseModel):
    current_streak_weeks: int
    longest_streak_weeks: int
    total_active_weeks: int
    active_this_week: bool
    rewards: List[str] = Field(default_factory=list)
    next_reward_at_weeks: Optional[int] = None
    recent_weeks: List[WeeklyStreakWeekOut] = Field(default_factory=list)


class TimelineOut(BaseModel):
    milestone_id: UUID
    title: str
    description: Optional[str] = None
    semester_index: int


class AiGuideIn(BaseModel):
    question: Optional[str] = None
    context_text: Optional[str] = None


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


class AiIfIWereYouIn(BaseModel):
    gpa: Optional[float] = Field(default=None, ge=0, le=4)
    internship_history: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None


class AiIfIWereYouOut(BaseModel):
    summary: str
    fastest_path: List[str] = Field(default_factory=list)
    realistic_next_moves: List[str] = Field(default_factory=list)
    avoid_now: List[str] = Field(default_factory=list)
    recommended_certificates: List[str] = Field(default_factory=list)
    uncertainty: Optional[str] = None


class AiCertRoiIn(BaseModel):
    target_role: Optional[str] = None
    current_skills: Optional[str] = None
    location: Optional[str] = None
    max_budget_usd: Optional[int] = Field(default=None, ge=0)


class AiCertRoiOptionOut(BaseModel):
    certificate: str
    cost_usd: str
    time_required: str
    entry_salary_range: str
    difficulty_level: str
    demand_trend: str
    roi_score: int = Field(ge=1, le=100)
    why_it_helps: str


class AiCertRoiOut(BaseModel):
    target_role: Optional[str] = None
    top_options: List[AiCertRoiOptionOut] = Field(default_factory=list)
    winner: Optional[str] = None
    recommendation: str
    uncertainty: Optional[str] = None


class AiEmotionalResetIn(BaseModel):
    story_context: Optional[str] = None


class AiEmotionalResetOut(BaseModel):
    title: str
    story: str
    reframe: str
    action_plan: List[str] = Field(default_factory=list)
    uncertainty: Optional[str] = None


class AiRebuildPlanIn(BaseModel):
    current_skills: str
    target_job: str
    location: Optional[str] = None
    hours_per_week: Optional[int] = Field(default=8, ge=1, le=80)


class AiRebuildPlanOut(BaseModel):
    summary: str
    day_0_30: List[str] = Field(default_factory=list)
    day_31_60: List[str] = Field(default_factory=list)
    day_61_90: List[str] = Field(default_factory=list)
    weekly_targets: List[str] = Field(default_factory=list)
    portfolio_targets: List[str] = Field(default_factory=list)
    recommended_certificates: List[str] = Field(default_factory=list)
    uncertainty: Optional[str] = None


class AiCollegeGapIn(BaseModel):
    target_job: Optional[str] = None
    current_skills: Optional[str] = None


class AiCollegeGapOut(BaseModel):
    job_description_playbook: List[str] = Field(default_factory=list)
    reverse_engineer_skills: List[str] = Field(default_factory=list)
    project_that_recruiters_care: List[str] = Field(default_factory=list)
    networking_strategy: List[str] = Field(default_factory=list)
    uncertainty: Optional[str] = None


class MarketStressTestIn(BaseModel):
    target_job: str
    location: str


class MarketStressTestOut(BaseModel):
    score: float
    mri_formula: Optional[str] = None
    mri_formula_version: Optional[str] = None
    computed_at: Optional[str] = None
    components: dict[str, float] = Field(default_factory=dict)
    weights: dict[str, float] = Field(default_factory=dict)
    required_skills_count: int = 0
    matched_skills_count: int = 0
    missing_skills: List[str] = Field(default_factory=list)
    salary_average: Optional[float] = None
    salary_percentile_local: Optional[float] = None
    top_hiring_companies: List[dict[str, Any]] = Field(default_factory=list)
    vacancy_growth_percent: float = 0.0
    market_volatility_score: float = 0.0
    adzuna_query_mode: str = "exact"
    adzuna_query_used: Optional[str] = None
    adzuna_location_used: Optional[str] = None
    vacancy_trend_label: str = "neutral"
    job_stability_score_2027: float = 0.0
    data_freshness: str = "unknown"
    source_mode: str = "live"
    snapshot_timestamp: Optional[str] = None
    snapshot_age_minutes: Optional[float] = None
    provider_status: dict[str, str] = Field(default_factory=dict)
    market_volatility_points: List[dict[str, float]] = Field(default_factory=list)
    evidence_counts: dict[str, int] = Field(default_factory=dict)
    simulation_2027: dict[str, Any] = Field(default_factory=dict)
    citations: List[dict[str, Any]] = Field(default_factory=list)


class RepoProofCheckerIn(BaseModel):
    target_job: str
    location: str
    repo_url: str
    proof_id: Optional[UUID] = None


class RepoProofCheckerOut(BaseModel):
    repo_url: str
    required_skills_count: int = 0
    matched_skills: List[str] = Field(default_factory=list)
    verified_by_repo_skills: List[str] = Field(default_factory=list)
    skills_required_but_missing: List[str] = Field(default_factory=list)
    match_count: int = 0
    repo_confidence: float = 0.0
    files_checked: List[str] = Field(default_factory=list)
    repos_checked: List[str] = Field(default_factory=list)
    languages_detected: List[str] = Field(default_factory=list)
    vacancy_trend_label: str = "neutral"
    adzuna_query_mode: str = "exact"
    adzuna_query_used: Optional[str] = None
    adzuna_location_used: Optional[str] = None
    source_mode: str = "live"
    snapshot_timestamp: Optional[str] = None
    snapshot_age_minutes: Optional[float] = None


class AICareerOrchestratorIn(BaseModel):
    target_job: str
    location: str
    availability_hours_per_week: int = Field(default=20, ge=1, le=80)
    pivot_requested: bool = False


class AICareerOrchestratorOut(BaseModel):
    stress_test: dict[str, Any]
    auditor: dict[str, Any]
    planner: dict[str, Any]
    strategist: dict[str, Any]
    mission_dashboard: dict[str, Any] = Field(default_factory=dict)
    market_alert: str = ""
    top_missing_skills: List[str] = Field(default_factory=list)
    pivot_applied: bool = False
    pivot_reason: Optional[str] = None
    pivot_target_role: Optional[str] = None
    pivot_delta: Optional[float] = None


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


class AiInterviewSessionIn(BaseModel):
    target_role: Optional[str] = None
    job_description: Optional[str] = None
    question_count: int = Field(default=5, ge=3, le=10)


class AiInterviewQuestionOut(BaseModel):
    id: UUID
    order_index: int
    prompt: str
    focus_item_id: Optional[UUID] = None
    focus_title: Optional[str] = None
    focus_milestone_id: Optional[UUID] = None
    focus_milestone_title: Optional[str] = None
    source_proof_id: Optional[UUID] = None
    difficulty: Optional[str] = None


class AiInterviewResponseIn(BaseModel):
    question_id: UUID
    answer_text: Optional[str] = None
    video_url: Optional[str] = None


class AiInterviewResponseOut(BaseModel):
    id: UUID
    session_id: UUID
    question_id: UUID
    answer_text: Optional[str] = None
    video_url: Optional[str] = None
    ai_feedback: Optional[str] = None
    ai_score: Optional[float] = None
    confidence: Optional[float] = None
    submitted_at: datetime


class AiInterviewSessionOut(BaseModel):
    id: UUID
    target_role: Optional[str] = None
    job_description: Optional[str] = None
    question_count: int
    status: str
    summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    questions: List[AiInterviewQuestionOut] = Field(default_factory=list)
    responses: List[AiInterviewResponseOut] = Field(default_factory=list)


class AiResumeArchitectIn(BaseModel):
    target_role: Optional[str] = None
    job_description: Optional[str] = None


class AiResumeArtifactOut(BaseModel):
    id: UUID
    target_role: Optional[str] = None
    job_description: Optional[str] = None
    ats_keywords: List[str] = Field(default_factory=list)
    markdown_content: str
    structured: Optional[dict[str, Any]] = None
    created_at: datetime


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


class MarketAutomationRunIn(BaseModel):
    dry_run: bool = False
    trigger: Optional[str] = None


class MarketAutomationOut(BaseModel):
    ok: bool
    trigger: str
    dry_run: bool
    started_at: datetime
    finished_at: datetime
    duration_seconds: float
    providers_requested: List[str] = Field(default_factory=list)
    providers_used: List[str] = Field(default_factory=list)
    pathways_considered: int = 0
    ingestions: int = 0
    signals_created: int = 0
    proposals_created: int = 0
    proposals_skipped: int = 0
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class MarketAutomationStatusOut(BaseModel):
    enabled: bool
    scheduler_running: bool
    interval_minutes: int
    providers_requested: List[str] = Field(default_factory=list)
    providers_available: List[str] = Field(default_factory=list)
    providers_missing: List[str] = Field(default_factory=list)
    role_families: List[str] = Field(default_factory=list)
    pathway_filters: List[str] = Field(default_factory=list)
    invalid_pathway_filters: List[str] = Field(default_factory=list)
    last_cycle_at: Optional[datetime] = None
    last_cycle_metadata: Optional[dict[str, Any]] = None
    last_scheduler_error: Optional[str] = None


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
