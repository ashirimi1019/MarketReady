// Shared API types — canonical source: backend/app/schemas/api.py
// All UUIDs are strings (JSON serialized), all datetimes are ISO strings.

// ── Auth ─────────────────────────────────────────────────────────────

export type AuthOut = {
  user_id: string;
  auth_token?: string | null;
  refresh_token?: string | null;
  access_expires_at?: string | null;
  refresh_expires_at?: string | null;
  email_verification_required?: boolean;
  message?: string | null;
  dev_code?: string | null;
};

export type AuthActionOut = {
  ok: boolean;
  message: string;
  dev_code?: string | null;
};

// ── Pathway & Major ──────────────────────────────────────────────────

export type Major = {
  id: string;
  name: string;
  description?: string | null;
};

export type Pathway = {
  id: string;
  name: string;
  description?: string | null;
  is_compatible?: boolean;
  notes?: string | null;
};

export type UserPathway = {
  major_id: string;
  pathway_id: string;
  cohort?: string | null;
  cohort_id?: string | null;
  checklist_version_id?: string | null;
  selected_at?: string;
};

// ── Checklist ────────────────────────────────────────────────────────

export type ChecklistItem = {
  id: string;
  title: string;
  description?: string | null;
  tier?: string;
  rationale?: string | null;
  is_critical?: boolean;
  allowed_proof_types?: string[];
  status?: string;
};

export type ChecklistVersion = {
  id: string;
  pathway_id: string;
  version_number: number;
  status: string;
  published_at?: string | null;
  item_count: number;
};

export type ChecklistChangeLog = {
  id: string;
  pathway_id?: string;
  from_version_id?: string | null;
  to_version_id?: string | null;
  change_type: string;
  summary?: string | null;
  metadata?: Record<string, unknown> | null;
  created_by?: string | null;
  created_at: string;
};

// ── Proof ────────────────────────────────────────────────────────────

export type Proof = {
  id: string;
  user_id?: string;
  checklist_item_id: string;
  proof_type: string;
  url: string;
  view_url?: string | null;
  status: string;
  review_note?: string | null;
  metadata?: Record<string, unknown> | null;
  created_at?: string;
};

// ── Profile ──────────────────────────────────────────────────────────

export type StudentProfile = {
  id?: string;
  user_id?: string;
  semester?: string | null;
  state?: string | null;
  university?: string | null;
  masters_interest?: boolean;
  masters_target?: string | null;
  masters_timeline?: string | null;
  masters_status?: string | null;
  github_username?: string | null;
  resume_url?: string | null;
  resume_view_url?: string | null;
  resume_filename?: string | null;
  resume_uploaded_at?: string | null;
  created_at?: string;
  updated_at?: string;
};

// ── Readiness ────────────────────────────────────────────────────────

export type Readiness = {
  score: number;
  checklist_score?: number;
  engineering_score?: number;
  market_alignment_score?: number;
  band: string;
  capped?: boolean;
  cap_reason?: string | null;
  top_gaps?: string[];
  next_actions?: string[];
};

// ── AI Guide ─────────────────────────────────────────────────────────

export type AiGuide = {
  explanation?: string;
  decision?: string | null;
  recommendations?: string[];
  recommended_certificates?: string[];
  materials_to_master?: string[];
  market_top_skills?: string[];
  market_alignment?: string[];
  priority_focus_areas?: string[];
  weekly_plan?: string[];
  evidence_snippets?: string[];
  confidence_by_item?: Record<string, number>;
  next_actions?: string[];
  suggested_proof_types?: string[];
  cited_checklist_item_ids?: string[];
  resume_detected?: boolean;
  resume_strengths?: string[];
  resume_improvements?: string[];
  uncertainty?: string | null;
};

// ── Goals & Engagement ───────────────────────────────────────────────

export type Goal = {
  id: string;
  title: string;
  description?: string | null;
  status: string;
  target_date?: string | null;
  last_check_in_at?: string | null;
  streak_days: number;
  created_at?: string;
  updated_at?: string;
};

export type Notification = {
  id: string;
  kind: string;
  message: string;
  is_read: boolean;
  metadata?: Record<string, unknown> | null;
  created_at: string;
};

export type EngagementSummary = {
  goals_total: number;
  goals_completed: number;
  active_streak_days: number;
  unread_notifications: number;
  next_deadlines: string[];
};

// ── Timeline ─────────────────────────────────────────────────────────

export type Milestone = {
  milestone_id: string;
  title: string;
  description?: string | null;
  semester_index: number;
};

// ── Storage / Meta ───────────────────────────────────────────────────

export type StorageMeta = {
  s3_enabled: boolean;
  s3_bucket?: string | null;
  s3_region?: string | null;
  local_enabled: boolean;
};

export type EvidenceMapResponse = {
  matched_count: number;
  mode: string;
  matched_item_ids: string[];
};

// ── Market ───────────────────────────────────────────────────────────

export type MarketSignal = {
  id: string;
  pathway_id?: string | null;
  skill_id?: string | null;
  skill_name?: string | null;
  role_family?: string | null;
  window_start?: string | null;
  window_end?: string | null;
  frequency?: number | null;
  source_count?: number | null;
  metadata?: Record<string, unknown> | null;
};

export type MarketProposal = {
  id: string;
  pathway_id: string;
  proposed_version_number?: number | null;
  status: string;
  summary?: string | null;
  diff?: Record<string, unknown> | null;
  created_at: string;
  approved_at?: string | null;
  approved_by?: string | null;
  published_at?: string | null;
  published_by?: string | null;
};

// ── Admin (Skill) ────────────────────────────────────────────────────

export type Skill = {
  id: string;
  name: string;
  description?: string | null;
};

export type ReadinessRank = {
  score: number;
  band: string;
  percentile: number;
  rank: number;
  total_students: number;
  linkedin_share_text: string;
  linkedin_share_url: string;
};

export type WeeklyStreakWeek = {
  week_start: string;
  week_label: string;
  has_activity: boolean;
};

export type WeeklyMilestoneStreak = {
  current_streak_weeks: number;
  longest_streak_weeks: number;
  total_active_weeks: number;
  active_this_week: boolean;
  rewards: string[];
  next_reward_at_weeks?: number | null;
  recent_weeks: WeeklyStreakWeek[];
};

export type AiInterviewQuestion = {
  id: string;
  order_index: number;
  prompt: string;
  focus_item_id?: string | null;
  focus_title?: string | null;
  focus_milestone_id?: string | null;
  focus_milestone_title?: string | null;
  source_proof_id?: string | null;
  difficulty?: string | null;
};

export type AiInterviewResponse = {
  id: string;
  session_id: string;
  question_id: string;
  answer_text?: string | null;
  video_url?: string | null;
  ai_feedback?: string | null;
  ai_score?: number | null;
  confidence?: number | null;
  submitted_at: string;
};

export type AiInterviewSession = {
  id: string;
  target_role?: string | null;
  job_description?: string | null;
  question_count: number;
  status: string;
  summary?: string | null;
  created_at: string;
  updated_at: string;
  questions: AiInterviewQuestion[];
  responses: AiInterviewResponse[];
};

export type AiResumeArtifact = {
  id: string;
  target_role?: string | null;
  job_description?: string | null;
  ats_keywords: string[];
  markdown_content: string;
  structured?: Record<string, unknown> | null;
  created_at: string;
};

export type MarketStressTest = {
  score: number;
  mri_formula?: string | null;
  mri_formula_version?: string | null;
  computed_at?: string | null;
  components: Record<string, number>;
  weights: Record<string, number>;
  required_skills_count: number;
  matched_skills_count: number;
  missing_skills: string[];
  salary_average?: number | null;
  salary_percentile_local?: number | null;
  top_hiring_companies?: Array<{ name: string; open_roles: number }>;
  vacancy_growth_percent?: number;
  market_volatility_score?: number;
  vacancy_trend_label: string;
  job_stability_score_2027: number;
  data_freshness: string;
  source_mode: "live" | "snapshot_fallback";
  snapshot_timestamp?: string | null;
  snapshot_age_minutes?: number | null;
  provider_status: Record<string, string>;
  market_volatility_points: Array<{ x: number; y: number }>;
  evidence_counts: Record<string, number>;
  simulation_2027?: {
    projected_score: number;
    delta: number;
    risk_level: string;
    at_risk_skills: string[];
    growth_skills: string[];
  } | null;
  citations?: Array<{
    source: string;
    signal: string;
    value: string | number;
    note?: string;
  }>;
};

export type RepoProofChecker = {
  repo_url: string;
  required_skills_count: number;
  matched_skills: string[];
  verified_by_repo_skills: string[];
  skills_required_but_missing: string[];
  match_count: number;
  repo_confidence: number;
  files_checked: string[];
  repos_checked: string[];
  languages_detected: string[];
  vacancy_trend_label: string;
  source_mode: "live" | "snapshot_fallback";
  snapshot_timestamp?: string | null;
  snapshot_age_minutes?: number | null;
};

export type AICareerOrchestrator = {
  stress_test: Record<string, unknown>;
  auditor: Record<string, unknown>;
  planner: Record<string, unknown>;
  strategist: Record<string, unknown>;
  mission_dashboard: Record<string, unknown>;
  market_alert: string;
  top_missing_skills: string[];
  pivot_applied?: boolean;
  pivot_reason?: string | null;
  pivot_target_role?: string | null;
  pivot_delta?: number | null;
};
