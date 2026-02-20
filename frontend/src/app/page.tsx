"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { apiGet, apiSend } from "@/lib/api";
import { getErrorMessage, getRetryAfterSeconds, isRateLimited } from "@/lib/errors";
import { useSession } from "@/lib/session";
import { formatDisplayName } from "@/lib/name";

type AiGuide = {
  decision?: string | null;
  recommendations?: string[];
  next_actions?: string[];
  recommended_certificates?: string[];
  uncertainty?: string | null;
};

type AiIfIWereYouOut = {
  summary: string;
  fastest_path: string[];
  realistic_next_moves: string[];
  avoid_now: string[];
  recommended_certificates: string[];
  uncertainty?: string | null;
};

type AiCertRoiOption = {
  certificate: string;
  cost_usd: string;
  time_required: string;
  entry_salary_range: string;
  difficulty_level: string;
  demand_trend: string;
  roi_score: number;
  why_it_helps: string;
};

type AiCertRoiOut = {
  target_role?: string | null;
  top_options: AiCertRoiOption[];
  winner?: string | null;
  recommendation: string;
  uncertainty?: string | null;
};

type AiEmotionalResetOut = {
  title: string;
  story: string;
  reframe: string;
  action_plan: string[];
  uncertainty?: string | null;
};

type AiRebuildPlanOut = {
  summary: string;
  day_0_30: string[];
  day_31_60: string[];
  day_61_90: string[];
  weekly_targets: string[];
  portfolio_targets: string[];
  recommended_certificates: string[];
  uncertainty?: string | null;
};

type AiCollegeGapOut = {
  job_description_playbook: string[];
  reverse_engineer_skills: string[];
  project_that_recruiters_care: string[];
  networking_strategy: string[];
  uncertainty?: string | null;
};

type Proof = {
  status: string;
};

type ChecklistItem = {
  id: string;
};

type Readiness = {
  score: number;
};

type ReadinessRank = {
  percentile: number;
  rank: number;
  total_students: number;
};

type WeeklyMilestoneStreak = {
  current_streak_weeks: number;
};

const TICKER_ITEMS = [
  "Need direction after school? Use OpenAI to map your next practical move",
  "Real hiring signals + cert ROI + project proof in one student workflow",
  "No internship yet? Build a realistic path with AI, not guesswork",
  "Learn what to build, what to certify, and what recruiters actually check",
  "Turn weekly output into measurable readiness by graduation",
];

const QUICK_LINKS = [
  {
    title: "My Pathway",
    text: "Confirm your major, pathway, and year-by-year roadmap.",
    href: "/student/onboarding",
  },
  {
    title: "Submit Proof",
    text: "Upload evidence for completed checklist requirements.",
    href: "/student/checklist",
  },
  {
    title: "Proof Vault",
    text: "Track submitted, verified, and rejected artifacts.",
    href: "/student/proofs",
  },
  {
    title: "Readiness Score",
    text: "View your score out of 100 with top gaps and actions.",
    href: "/student/readiness",
  },
  {
    title: "Interview Simulator",
    text: "Practice OpenAI interview questions tied to your submitted proofs.",
    href: "/student/interview",
  },
  {
    title: "OpenAI Resume Architect",
    text: "Generate ATS-ready resume drafts from your portal evidence.",
    href: "/student/resume-architect",
  },
  {
    title: "OpenAI Guide",
    text: "Generate targeted recommendations on demand.",
    href: "/student/guide",
  },
  {
    title: "Timeline",
    text: "Stay aligned to year-based milestone targets.",
    href: "/student/timeline",
  },
];

function readinessToRank(score: number | null): string {
  if (score === null) return "Top --";
  if (score >= 90) return "Top 5%";
  if (score >= 80) return "Top 12%";
  if (score >= 70) return "Top 22%";
  if (score >= 60) return "Top 35%";
  return "Climbing";
}

function buildApiError(error: unknown, fallback: string): string {
  if (isRateLimited(error)) {
    const retry = getRetryAfterSeconds(error);
    return retry
      ? `Rate limit reached. Try again in about ${retry} seconds.`
      : "Rate limit reached. Please wait and try again.";
  }
  return getErrorMessage(error) || fallback;
}

export default function Home() {
  const { username, isLoggedIn } = useSession();
  const displayName = formatDisplayName(username);
  const headers = useMemo(() => ({ "X-User-Id": username }), [username]);

  const [auditInput, setAuditInput] = useState("");
  const [guide, setGuide] = useState<AiGuide | null>(null);
  const [guideError, setGuideError] = useState<string | null>(null);
  const [guideLoading, setGuideLoading] = useState(false);

  const [ifGpa, setIfGpa] = useState("");
  const [ifInternship, setIfInternship] = useState("");
  const [ifIndustry, setIfIndustry] = useState("");
  const [ifLocation, setIfLocation] = useState("");
  const [ifResult, setIfResult] = useState<AiIfIWereYouOut | null>(null);
  const [ifError, setIfError] = useState<string | null>(null);
  const [ifLoading, setIfLoading] = useState(false);

  const [roiTargetRole, setRoiTargetRole] = useState("");
  const [roiCurrentSkills, setRoiCurrentSkills] = useState("");
  const [roiLocation, setRoiLocation] = useState("");
  const [roiBudget, setRoiBudget] = useState("");
  const [roiResult, setRoiResult] = useState<AiCertRoiOut | null>(null);
  const [roiError, setRoiError] = useState<string | null>(null);
  const [roiLoading, setRoiLoading] = useState(false);

  const [emotionalContext, setEmotionalContext] = useState("");
  const [emotionalResult, setEmotionalResult] = useState<AiEmotionalResetOut | null>(null);
  const [emotionalError, setEmotionalError] = useState<string | null>(null);
  const [emotionalLoading, setEmotionalLoading] = useState(false);

  const [planSkills, setPlanSkills] = useState("");
  const [planTargetJob, setPlanTargetJob] = useState("");
  const [planLocation, setPlanLocation] = useState("");
  const [planHours, setPlanHours] = useState("8");
  const [planResult, setPlanResult] = useState<AiRebuildPlanOut | null>(null);
  const [planError, setPlanError] = useState<string | null>(null);
  const [planLoading, setPlanLoading] = useState(false);

  const [gapTargetJob, setGapTargetJob] = useState("");
  const [gapCurrentSkills, setGapCurrentSkills] = useState("");
  const [gapResult, setGapResult] = useState<AiCollegeGapOut | null>(null);
  const [gapError, setGapError] = useState<string | null>(null);
  const [gapLoading, setGapLoading] = useState(false);

  const [proofStats, setProofStats] = useState({
    submitted: 0,
    verified: 0,
    rejected: 0,
  });
  const [checklistCount, setChecklistCount] = useState<number | null>(null);
  const [readinessScore, setReadinessScore] = useState<number | null>(null);
  const [readinessRank, setReadinessRank] = useState<ReadinessRank | null>(null);
  const [weeklyStreak, setWeeklyStreak] = useState<WeeklyMilestoneStreak | null>(null);

  const requireLogin = (setter: (message: string | null) => void) => {
    if (isLoggedIn) return false;
    setter("Log in to use this OpenAI feature.");
    return true;
  };

  const runAudit = async () => {
    if (requireLogin(setGuideError)) return;
    setGuideLoading(true);
    setGuideError(null);
    try {
      const text = auditInput.trim();
      const data = await apiSend<AiGuide>("/user/ai/guide", {
        method: "POST",
        headers: {
          ...headers,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: text || null,
          context_text: text || null,
        }),
      });
      setGuide(data);
    } catch (error) {
      setGuideError(buildApiError(error, "OpenAI audit unavailable."));
    } finally {
      setGuideLoading(false);
    }
  };

  const runIfIWereYou = async () => {
    if (requireLogin(setIfError)) return;
    setIfLoading(true);
    setIfError(null);
    try {
      const parsedGpa = ifGpa.trim() ? Number(ifGpa) : null;
      const data = await apiSend<AiIfIWereYouOut>("/user/ai/if-i-were-you", {
        method: "POST",
        headers: {
          ...headers,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          gpa:
            parsedGpa !== null && Number.isFinite(parsedGpa)
              ? parsedGpa
              : null,
          internship_history: ifInternship.trim() || null,
          industry: ifIndustry.trim() || null,
          location: ifLocation.trim() || null,
        }),
      });
      setIfResult(data);
    } catch (error) {
      setIfError(buildApiError(error, "OpenAI path planner unavailable."));
    } finally {
      setIfLoading(false);
    }
  };

  const runCertificationRoi = async () => {
    if (requireLogin(setRoiError)) return;
    setRoiLoading(true);
    setRoiError(null);
    try {
      const parsedBudget = roiBudget.trim() ? Number(roiBudget) : null;
      const data = await apiSend<AiCertRoiOut>("/user/ai/certification-roi", {
        method: "POST",
        headers: {
          ...headers,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          target_role: roiTargetRole.trim() || null,
          current_skills: roiCurrentSkills.trim() || null,
          location: roiLocation.trim() || null,
          max_budget_usd:
            parsedBudget !== null && Number.isFinite(parsedBudget)
              ? parsedBudget
              : null,
        }),
      });
      setRoiResult(data);
    } catch (error) {
      setRoiError(buildApiError(error, "OpenAI certification ROI unavailable."));
    } finally {
      setRoiLoading(false);
    }
  };

  const runEmotionalReset = async () => {
    if (requireLogin(setEmotionalError)) return;
    setEmotionalLoading(true);
    setEmotionalError(null);
    try {
      const data = await apiSend<AiEmotionalResetOut>("/user/ai/emotional-reset", {
        method: "POST",
        headers: {
          ...headers,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          story_context: emotionalContext.trim() || null,
        }),
      });
      setEmotionalResult(data);
    } catch (error) {
      setEmotionalError(buildApiError(error, "OpenAI support module unavailable."));
    } finally {
      setEmotionalLoading(false);
    }
  };

  const runRebuildPlan = async () => {
    if (requireLogin(setPlanError)) return;
    if (!planSkills.trim() || !planTargetJob.trim()) {
      setPlanError("Current skills and target job are required.");
      return;
    }
    setPlanLoading(true);
    setPlanError(null);
    try {
      const parsedHours = Number(planHours);
      const data = await apiSend<AiRebuildPlanOut>("/user/ai/rebuild-90-day", {
        method: "POST",
        headers: {
          ...headers,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          current_skills: planSkills.trim(),
          target_job: planTargetJob.trim(),
          location: planLocation.trim() || null,
          hours_per_week: Number.isFinite(parsedHours) ? parsedHours : 8,
        }),
      });
      setPlanResult(data);
    } catch (error) {
      setPlanError(buildApiError(error, "OpenAI 90-day plan unavailable."));
    } finally {
      setPlanLoading(false);
    }
  };

  const runCollegeGap = async () => {
    if (requireLogin(setGapError)) return;
    setGapLoading(true);
    setGapError(null);
    try {
      const data = await apiSend<AiCollegeGapOut>("/user/ai/college-gap-playbook", {
        method: "POST",
        headers: {
          ...headers,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          target_job: gapTargetJob.trim() || null,
          current_skills: gapCurrentSkills.trim() || null,
        }),
      });
      setGapResult(data);
    } catch (error) {
      setGapError(buildApiError(error, "OpenAI practical playbook unavailable."));
    } finally {
      setGapLoading(false);
    }
  };

  useEffect(() => {
    if (isLoggedIn) return;
    setGuide(null);
    setGuideError(null);
    setIfResult(null);
    setIfError(null);
    setRoiResult(null);
    setRoiError(null);
    setEmotionalResult(null);
    setEmotionalError(null);
    setPlanResult(null);
    setPlanError(null);
    setGapResult(null);
    setGapError(null);
  }, [isLoggedIn]);

  useEffect(() => {
    if (!isLoggedIn) {
      setProofStats({ submitted: 0, verified: 0, rejected: 0 });
      setChecklistCount(null);
      setReadinessScore(null);
      setReadinessRank(null);
      setWeeklyStreak(null);
      return;
    }

    let cancelled = false;

    const loadDashboard = async () => {
      const [
        proofsResult,
        checklistResult,
        readinessResult,
        rankResult,
        streakResult,
      ] = await Promise.allSettled([
        apiGet<Proof[]>("/user/proofs", headers),
        apiGet<ChecklistItem[]>("/user/checklist", headers),
        apiGet<Readiness>("/user/readiness", headers),
        apiGet<ReadinessRank>("/user/readiness/rank", headers),
        apiGet<WeeklyMilestoneStreak>("/user/streak", headers),
      ]);

      if (cancelled) return;

      if (proofsResult.status === "fulfilled") {
        const stats = { submitted: 0, verified: 0, rejected: 0 };
        proofsResult.value.forEach((proof) => {
          if (proof.status === "verified") stats.verified += 1;
          else if (proof.status === "rejected") stats.rejected += 1;
          else stats.submitted += 1;
        });
        setProofStats(stats);
      } else {
        setProofStats({ submitted: 0, verified: 0, rejected: 0 });
      }

      setChecklistCount(
        checklistResult.status === "fulfilled" ? checklistResult.value.length : null
      );
      setReadinessScore(
        readinessResult.status === "fulfilled" ? readinessResult.value.score : null
      );
      setReadinessRank(rankResult.status === "fulfilled" ? rankResult.value : null);
      setWeeklyStreak(streakResult.status === "fulfilled" ? streakResult.value : null);
    };

    loadDashboard().catch(() => {
      if (cancelled) return;
      setProofStats({ submitted: 0, verified: 0, rejected: 0 });
      setChecklistCount(null);
      setReadinessScore(null);
      setReadinessRank(null);
      setWeeklyStreak(null);
    });

    return () => {
      cancelled = true;
    };
  }, [headers, isLoggedIn]);

  const versionedSkills = isLoggedIn ? checklistCount ?? 0 : 14;
  const verifiedAssets = isLoggedIn ? proofStats.verified : 32;
  const marketRank = isLoggedIn
    ? readinessRank
      ? `Top ${Math.max(1, Math.round(100 - readinessRank.percentile + 1))}%`
      : readinessToRank(readinessScore)
    : "Top 4%";

  return (
    <main className="landing-stack">
      <section className="market-ticker" aria-label="Live market signals">
        <div className="market-ticker-track">
          {[...TICKER_ITEMS, ...TICKER_ITEMS].map((item, index) => (
            <span key={`${item}-${index}`} className="market-ticker-item">
              {item}
            </span>
          ))}
        </div>
      </section>

      <section className="panel hero-stage">
        <span className="hero-signal-pill">OpenAI Career Engine</span>
        <h1 className="hero-headline">
          Not sure what to do
          <br />
          <span className="hero-emphasis">after school?</span>
        </h1>
        <p className="hero-copy">
          {isLoggedIn
            ? `${displayName}, get clear next steps from your current profile, proofs, and hiring signals.`
            : "Market Ready is for students and recent grads who want a real plan to land a job by graduation, not vague advice."}
        </p>
        <div className="mt-8 grid gap-3 md:grid-cols-2 xl:grid-cols-4 text-left">
          <article className="auditor-result-card">
            <p className="auditor-result-label">Who it is for</p>
            <p className="mt-2 text-[color:var(--muted)]">
              High school and college students, plus recent grads.
            </p>
          </article>
          <article className="auditor-result-card">
            <p className="auditor-result-label">Problem it solves</p>
            <p className="mt-2 text-[color:var(--muted)]">
              Unclear career direction, random certifications, and weak job-market alignment.
            </p>
          </article>
          <article className="auditor-result-card">
            <p className="auditor-result-label">Why this is better</p>
            <p className="mt-2 text-[color:var(--muted)]">
              OpenAI guidance + proof-backed tracking + measurable readiness in one flow.
            </p>
          </article>
          <article className="auditor-result-card">
            <p className="auditor-result-label">What to do now</p>
            <p className="mt-2 text-[color:var(--muted)]">
              Run your AI audit, review your path, then execute your next milestone.
            </p>
          </article>
        </div>
        {isLoggedIn && (
          <p className="mt-4 text-sm text-[color:var(--muted)]">
            Weekly proof streak: {weeklyStreak?.current_streak_weeks ?? 0} week(s)
          </p>
        )}
        <div className="hero-actions">
          {isLoggedIn ? (
            <>
              <Link href="/student/checklist" className="cta">
                Continue My Plan
              </Link>
              <Link href="/student/readiness" className="cta cta-secondary">
                View My Score
              </Link>
            </>
          ) : (
            <>
              <Link href="/register" className="cta">
                Create My Plan
              </Link>
              <Link href="/login" className="cta cta-secondary">
                Login
              </Link>
            </>
          )}
        </div>
      </section>

      <section className="panel auditor-stage" id="audit-engine">
        <div className="auditor-header">
          <span className="auditor-icon" aria-hidden>
            *
          </span>
          <div>
            <h2 className="section-title">AI Market Auditor - Powered by OpenAI</h2>
            <p className="section-subtitle">
              Paste your resume highlights or project details and get focused role guidance.
            </p>
          </div>
        </div>
        <label className="auditor-label" htmlFor="audit-input">
          Paste Resume Or Projects
        </label>
        <textarea
          id="audit-input"
          className="auditor-input"
          value={auditInput}
          onChange={(event) => setAuditInput(event.target.value)}
          placeholder="Ex: Built a website with HTML, CSS, JavaScript and deployed it."
        />
        <div className="auditor-actions">
          {isLoggedIn ? (
            <button className="cta auditor-cta" onClick={runAudit} disabled={guideLoading}>
              {guideLoading ? "Running Audit..." : "Audit My Readiness"}
            </button>
          ) : (
            <Link className="cta auditor-cta" href="/login">
              Login To Run Audit
            </Link>
          )}
        </div>
        {guideError && <p className="auditor-feedback auditor-feedback-error">{guideError}</p>}
        {guide && !guideLoading && (
          <div className="auditor-results">
            <div className="auditor-result-card">
              <p className="auditor-result-label">Decision</p>
              <p className="auditor-result-value">
                {guide.decision || "No decision returned."}
              </p>
            </div>
            <div className="auditor-result-card">
              <p className="auditor-result-label">Next Actions</p>
              <ul className="auditor-result-list">
                {guide.next_actions?.length
                  ? guide.next_actions.map((item) => <li key={item}>{item}</li>)
                  : guide.recommendations?.length
                    ? guide.recommendations.map((item) => <li key={item}>{item}</li>)
                    : [<li key="none">No actions returned.</li>]}
              </ul>
            </div>
            <div className="auditor-result-card">
              <p className="auditor-result-label">Recommended Certificates</p>
              <ul className="auditor-result-list">
                {guide.recommended_certificates?.length
                  ? guide.recommended_certificates.map((item) => <li key={item}>{item}</li>)
                  : [<li key="none-certs">No certificate recommendations returned.</li>]}
              </ul>
            </div>
          </div>
        )}
        {guide?.uncertainty && <p className="auditor-feedback">{guide.uncertainty}</p>}
      </section>

      <section className="panel">
        <div className="auditor-header">
          <span className="auditor-icon" aria-hidden>
            *
          </span>
          <div>
            <h2 className="section-title">If I Were You Mode - Powered by OpenAI</h2>
            <p className="section-subtitle">
              Get realistic next moves based on GPA, internship history, industry, and location.
            </p>
          </div>
        </div>
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <label className="text-sm text-[color:var(--muted)]">
            GPA (Optional)
            <input
              type="number"
              min={0}
              max={4}
              step="0.01"
              className="mt-2 w-full rounded-xl border border-[color:var(--border)] p-3"
              value={ifGpa}
              onChange={(event) => setIfGpa(event.target.value)}
              placeholder="3.45"
            />
          </label>
          <label className="text-sm text-[color:var(--muted)]">
            Target Industry
            <input
              className="mt-2 w-full rounded-xl border border-[color:var(--border)] p-3"
              value={ifIndustry}
              onChange={(event) => setIfIndustry(event.target.value)}
              placeholder="Frontend development"
            />
          </label>
          <label className="text-sm text-[color:var(--muted)] md:col-span-2">
            Internship History
            <textarea
              className="mt-2 w-full rounded-xl border border-[color:var(--border)] p-3 min-h-24"
              value={ifInternship}
              onChange={(event) => setIfInternship(event.target.value)}
              placeholder="No internships yet. Built two personal projects."
            />
          </label>
          <label className="text-sm text-[color:var(--muted)]">
            Location
            <input
              className="mt-2 w-full rounded-xl border border-[color:var(--border)] p-3"
              value={ifLocation}
              onChange={(event) => setIfLocation(event.target.value)}
              placeholder="Dallas, TX"
            />
          </label>
        </div>
        <div className="mt-4">
          {isLoggedIn ? (
            <button className="cta" onClick={runIfIWereYou} disabled={ifLoading}>
              {ifLoading ? "Generating Path..." : "Generate My Realistic Path"}
            </button>
          ) : (
            <Link className="cta" href="/login">
              Login To Use OpenAI Path
            </Link>
          )}
        </div>
        {ifError && <p className="auditor-feedback auditor-feedback-error">{ifError}</p>}
        {ifResult && (
          <div className="auditor-results mt-4">
            <article className="auditor-result-card">
              <p className="auditor-result-label">Summary</p>
              <p className="mt-2 text-lg">{ifResult.summary}</p>
            </article>
            <article className="auditor-result-card">
              <p className="auditor-result-label">Fastest Path</p>
              <ul className="auditor-result-list">
                {ifResult.fastest_path.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </article>
            <article className="auditor-result-card">
              <p className="auditor-result-label">Realistic Next Moves</p>
              <ul className="auditor-result-list">
                {ifResult.realistic_next_moves.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </article>
            <article className="auditor-result-card">
              <p className="auditor-result-label">Recommended Certificates</p>
              <ul className="auditor-result-list">
                {ifResult.recommended_certificates.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </article>
          </div>
        )}
        {ifResult?.uncertainty && <p className="auditor-feedback">{ifResult.uncertainty}</p>}
      </section>

      <section className="panel">
        <div className="auditor-header">
          <span className="auditor-icon" aria-hidden>
            *
          </span>
          <div>
            <h2 className="section-title">Certification ROI Calculator - Powered by OpenAI</h2>
            <p className="section-subtitle">
              Compare certificate cost, time, salary impact, difficulty, and demand trend.
            </p>
          </div>
        </div>
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <label className="text-sm text-[color:var(--muted)]">
            Target Role
            <input
              className="mt-2 w-full rounded-xl border border-[color:var(--border)] p-3"
              value={roiTargetRole}
              onChange={(event) => setRoiTargetRole(event.target.value)}
              placeholder="Frontend Developer"
            />
          </label>
          <label className="text-sm text-[color:var(--muted)]">
            Location
            <input
              className="mt-2 w-full rounded-xl border border-[color:var(--border)] p-3"
              value={roiLocation}
              onChange={(event) => setRoiLocation(event.target.value)}
              placeholder="United States"
            />
          </label>
          <label className="text-sm text-[color:var(--muted)] md:col-span-2">
            Current Skills
            <textarea
              className="mt-2 w-full rounded-xl border border-[color:var(--border)] p-3 min-h-24"
              value={roiCurrentSkills}
              onChange={(event) => setRoiCurrentSkills(event.target.value)}
              placeholder="HTML, CSS, JS, React basics"
            />
          </label>
          <label className="text-sm text-[color:var(--muted)]">
            Max Budget (USD, Optional)
            <input
              type="number"
              min={0}
              className="mt-2 w-full rounded-xl border border-[color:var(--border)] p-3"
              value={roiBudget}
              onChange={(event) => setRoiBudget(event.target.value)}
              placeholder="300"
            />
          </label>
        </div>
        <div className="mt-4">
          {isLoggedIn ? (
            <button className="cta" onClick={runCertificationRoi} disabled={roiLoading}>
              {roiLoading ? "Calculating ROI..." : "Calculate Certification ROI"}
            </button>
          ) : (
            <Link className="cta" href="/login">
              Login To Use ROI Calculator
            </Link>
          )}
        </div>
        {roiError && <p className="auditor-feedback auditor-feedback-error">{roiError}</p>}
        {roiResult && (
          <div className="mt-4 grid gap-4">
            <article className="auditor-result-card">
              <p className="auditor-result-label">Recommendation</p>
              <p className="mt-2 text-lg">{roiResult.recommendation}</p>
              {roiResult.winner && (
                <p className="mt-2 text-sm text-[color:var(--muted)]">
                  Best current ROI: {roiResult.winner}
                </p>
              )}
            </article>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {roiResult.top_options.map((item) => (
                <article className="auditor-result-card" key={item.certificate}>
                  <p className="auditor-result-label">{item.certificate}</p>
                  <p className="mt-2 text-sm text-[color:var(--muted)]">
                    ROI Score: {item.roi_score}/100
                  </p>
                  <ul className="auditor-result-list">
                    <li>Cost: {item.cost_usd}</li>
                    <li>Time: {item.time_required}</li>
                    <li>Entry Salary: {item.entry_salary_range}</li>
                    <li>Difficulty: {item.difficulty_level}</li>
                    <li>Demand Trend: {item.demand_trend}</li>
                  </ul>
                  <p className="mt-2 text-sm text-[color:var(--muted)]">{item.why_it_helps}</p>
                </article>
              ))}
            </div>
          </div>
        )}
        {roiResult?.uncertainty && <p className="auditor-feedback">{roiResult.uncertainty}</p>}
      </section>

      <section className="panel">
        <div className="auditor-header">
          <span className="auditor-icon" aria-hidden>
            *
          </span>
          <div>
            <h2 className="section-title">Graduated But Feel Behind? - Powered by OpenAI</h2>
            <p className="section-subtitle">
              Emotional support with practical direction, not vague motivation.
            </p>
          </div>
        </div>
        <label className="auditor-label" htmlFor="emotional-context">
          Your Current Situation (Optional)
        </label>
        <textarea
          id="emotional-context"
          className="auditor-input"
          value={emotionalContext}
          onChange={(event) => setEmotionalContext(event.target.value)}
          placeholder="Ex: I finished college but have no internship experience and feel behind."
        />
        <div className="mt-4">
          {isLoggedIn ? (
            <button className="cta" onClick={runEmotionalReset} disabled={emotionalLoading}>
              {emotionalLoading ? "Generating Guidance..." : "Generate Emotional Reset Plan"}
            </button>
          ) : (
            <Link className="cta" href="/login">
              Login To Use Emotional Reset
            </Link>
          )}
        </div>
        {emotionalError && (
          <p className="auditor-feedback auditor-feedback-error">{emotionalError}</p>
        )}
        {emotionalResult && (
          <div className="auditor-results mt-4">
            <article className="auditor-result-card">
              <p className="auditor-result-label">{emotionalResult.title}</p>
              <p className="mt-2 text-[color:var(--muted)]">{emotionalResult.story}</p>
            </article>
            <article className="auditor-result-card">
              <p className="auditor-result-label">Reframe</p>
              <p className="mt-2 text-[color:var(--muted)]">{emotionalResult.reframe}</p>
            </article>
            <article className="auditor-result-card">
              <p className="auditor-result-label">Action Plan</p>
              <ul className="auditor-result-list">
                {emotionalResult.action_plan.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </article>
          </div>
        )}
        {emotionalResult?.uncertainty && (
          <p className="auditor-feedback">{emotionalResult.uncertainty}</p>
        )}
      </section>

      <section className="panel">
        <div className="auditor-header">
          <span className="auditor-icon" aria-hidden>
            *
          </span>
          <div>
            <h2 className="section-title">90-Day Rebuild Plan Generator - Powered by OpenAI</h2>
            <p className="section-subtitle">
              Input current skills and target job. Get a practical 90-day execution plan.
            </p>
          </div>
        </div>
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <label className="text-sm text-[color:var(--muted)] md:col-span-2">
            Current Skills
            <textarea
              className="mt-2 w-full rounded-xl border border-[color:var(--border)] p-3 min-h-24"
              value={planSkills}
              onChange={(event) => setPlanSkills(event.target.value)}
              placeholder="HTML, CSS, JS, Git basics"
            />
          </label>
          <label className="text-sm text-[color:var(--muted)]">
            Target Job
            <input
              className="mt-2 w-full rounded-xl border border-[color:var(--border)] p-3"
              value={planTargetJob}
              onChange={(event) => setPlanTargetJob(event.target.value)}
              placeholder="Frontend Developer Intern"
            />
          </label>
          <label className="text-sm text-[color:var(--muted)]">
            Location
            <input
              className="mt-2 w-full rounded-xl border border-[color:var(--border)] p-3"
              value={planLocation}
              onChange={(event) => setPlanLocation(event.target.value)}
              placeholder="Remote / New York"
            />
          </label>
          <label className="text-sm text-[color:var(--muted)]">
            Hours Per Week
            <input
              type="number"
              min={1}
              max={80}
              className="mt-2 w-full rounded-xl border border-[color:var(--border)] p-3"
              value={planHours}
              onChange={(event) => setPlanHours(event.target.value)}
            />
          </label>
        </div>
        <div className="mt-4">
          {isLoggedIn ? (
            <button className="cta" onClick={runRebuildPlan} disabled={planLoading}>
              {planLoading ? "Building 90-Day Plan..." : "Generate 90-Day Plan"}
            </button>
          ) : (
            <Link className="cta" href="/login">
              Login To Build 90-Day Plan
            </Link>
          )}
        </div>
        {planError && <p className="auditor-feedback auditor-feedback-error">{planError}</p>}
        {planResult && (
          <div className="mt-4 grid gap-4">
            <article className="auditor-result-card">
              <p className="auditor-result-label">Summary</p>
              <p className="mt-2 text-lg">{planResult.summary}</p>
            </article>
            <div className="grid gap-3 md:grid-cols-3">
              <article className="auditor-result-card">
                <p className="auditor-result-label">Day 0-30</p>
                <ul className="auditor-result-list">
                  {planResult.day_0_30.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </article>
              <article className="auditor-result-card">
                <p className="auditor-result-label">Day 31-60</p>
                <ul className="auditor-result-list">
                  {planResult.day_31_60.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </article>
              <article className="auditor-result-card">
                <p className="auditor-result-label">Day 61-90</p>
                <ul className="auditor-result-list">
                  {planResult.day_61_90.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </article>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <article className="auditor-result-card">
                <p className="auditor-result-label">Weekly Targets</p>
                <ul className="auditor-result-list">
                  {planResult.weekly_targets.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </article>
              <article className="auditor-result-card">
                <p className="auditor-result-label">Portfolio + Certificates</p>
                <ul className="auditor-result-list">
                  {planResult.portfolio_targets.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                  {planResult.recommended_certificates.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </article>
            </div>
          </div>
        )}
        {planResult?.uncertainty && <p className="auditor-feedback">{planResult.uncertainty}</p>}
      </section>

      <section className="panel">
        <div className="auditor-header">
          <span className="auditor-icon" aria-hidden>
            *
          </span>
          <div>
            <h2 className="section-title">College Didn&apos;t Teach Me This - Powered by OpenAI</h2>
            <p className="section-subtitle">
              Practical playbook: read job descriptions, reverse engineer skills, build recruiter-relevant projects, and network strategically.
            </p>
          </div>
        </div>
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <label className="text-sm text-[color:var(--muted)]">
            Target Job
            <input
              className="mt-2 w-full rounded-xl border border-[color:var(--border)] p-3"
              value={gapTargetJob}
              onChange={(event) => setGapTargetJob(event.target.value)}
              placeholder="Data Analyst"
            />
          </label>
          <label className="text-sm text-[color:var(--muted)]">
            Current Skills
            <input
              className="mt-2 w-full rounded-xl border border-[color:var(--border)] p-3"
              value={gapCurrentSkills}
              onChange={(event) => setGapCurrentSkills(event.target.value)}
              placeholder="Excel, SQL basics"
            />
          </label>
        </div>
        <div className="mt-4">
          {isLoggedIn ? (
            <button className="cta" onClick={runCollegeGap} disabled={gapLoading}>
              {gapLoading ? "Generating Playbook..." : "Generate Practical Playbook"}
            </button>
          ) : (
            <Link className="cta" href="/login">
              Login To Generate Playbook
            </Link>
          )}
        </div>
        {gapError && <p className="auditor-feedback auditor-feedback-error">{gapError}</p>}
        {gapResult && (
          <div className="auditor-results mt-4">
            <article className="auditor-result-card">
              <p className="auditor-result-label">How To Read Job Descriptions</p>
              <ul className="auditor-result-list">
                {gapResult.job_description_playbook.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </article>
            <article className="auditor-result-card">
              <p className="auditor-result-label">Reverse Engineer Skills</p>
              <ul className="auditor-result-list">
                {gapResult.reverse_engineer_skills.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </article>
            <article className="auditor-result-card">
              <p className="auditor-result-label">Projects Recruiters Care About</p>
              <ul className="auditor-result-list">
                {gapResult.project_that_recruiters_care.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </article>
            <article className="auditor-result-card">
              <p className="auditor-result-label">Networking Strategy</p>
              <ul className="auditor-result-list">
                {gapResult.networking_strategy.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </article>
          </div>
        )}
        {gapResult?.uncertainty && <p className="auditor-feedback">{gapResult.uncertainty}</p>}
      </section>

      <section className="panel vault-stage" id="signals">
        <div className="vault-head">
          <h2 className="section-title">The Proof Vault</h2>
          <p className="section-subtitle">
            Where skills become evidence and readiness becomes measurable.
          </p>
        </div>
        <div className="vault-grid">
          <article className="vault-card vault-card-blue">
            <p className="vault-value">{versionedSkills}</p>
            <p className="vault-label">Versioned Skills</p>
          </article>
          <article className="vault-card vault-card-green">
            <p className="vault-value">{verifiedAssets}</p>
            <p className="vault-label">Verified Assets</p>
          </article>
          <article className="vault-card vault-card-purple">
            <p className="vault-value">{marketRank}</p>
            <p className="vault-label">Market Rank</p>
          </article>
        </div>
        {isLoggedIn && readinessRank && (
          <p className="mt-4 text-sm text-[color:var(--muted)] text-center">
            Global rank: #{readinessRank.rank} of {readinessRank.total_students}
          </p>
        )}
      </section>

      {isLoggedIn && (
        <section className="action-grid">
          {QUICK_LINKS.map((card) => (
            <Link key={card.title} href={card.href} className="action-card">
              <h2 className="text-xl font-semibold">{card.title}</h2>
              <p className="mt-3 text-[color:var(--muted)]">{card.text}</p>
              <div className="mt-4 text-sm text-[color:var(--accent-2)]">Open</div>
            </Link>
          ))}
        </section>
      )}
    </main>
  );
}
