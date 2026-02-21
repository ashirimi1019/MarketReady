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
    title: "Skill Gap Builder",
    text: "Translate missing skills into build targets and recruiter-facing proof.",
    href: "/student/resume-architect",
  },
  {
    title: "Market Mission Center",
    text: "Run MRI, verify with GitHub, and launch your 90-day mission dashboard.",
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

  const [roiTargetRole, setRoiTargetRole] = useState("");
  const [roiCurrentSkills, setRoiCurrentSkills] = useState("");
  const [roiLocation, setRoiLocation] = useState("");
  const [roiBudget, setRoiBudget] = useState("");
  const [roiResult, setRoiResult] = useState<AiCertRoiOut | null>(null);
  const [roiError, setRoiError] = useState<string | null>(null);
  const [roiLoading, setRoiLoading] = useState(false);

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

  useEffect(() => {
    if (isLoggedIn) return;
    setGuide(null);
    setGuideError(null);
    setRoiResult(null);
    setRoiError(null);
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
  const React = { useState, useEffect };
  const [score, setScore] = React.useState(82);

  React.useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null;
    const delay = setTimeout(() => {
      let current = 82;
      interval = setInterval(() => {
        current -= 1;
        setScore(current);
        if (current <= 63) {
          if (interval) clearInterval(interval);
        }
      }, 30);
    }, 1200);

    return () => {
      clearTimeout(delay);
      if (interval) clearInterval(interval);
    };
  }, []);

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

      <section className="panel bg-zinc-950 text-white text-center py-24 px-6">
        <h1 className="text-5xl md:text-6xl font-extrabold tracking-tight leading-tight">
          Are You Actually Hireable — Or Just Hopeful?
        </h1>
        <p className="text-xl text-zinc-300 max-w-3xl mx-auto mt-6">
          We combine live GitHub engineering signals with real hiring demand data — then
          stress-test your career against the next AI market shift.
        </p>
        {isLoggedIn && (
          <p className="mt-4 text-sm text-zinc-400">
            Welcome back, {displayName}. Weekly proof streak: {weeklyStreak?.current_streak_weeks ?? 0} week(s)
          </p>
        )}
        <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
          <Link
            href={isLoggedIn ? "/student/readiness" : "/login"}
            className="mt-10 px-8 py-4 text-lg font-semibold bg-indigo-600 hover:bg-indigo-500 rounded-xl transition transform hover:scale-105"
          >
            🔮 Stress-Test My Career
          </Link>
          <a
            href="#future-shock"
            className="mt-10 px-8 py-4 text-lg font-semibold border border-zinc-700 text-zinc-100 hover:bg-zinc-800 rounded-xl transition"
          >
            See How It Works
          </a>
        </div>
      </section>

      <section id="future-shock" className="bg-zinc-950 text-white py-24 px-6 text-center rounded-3xl border border-zinc-800">
        <div className="bg-zinc-900 rounded-2xl border border-zinc-800 shadow-2xl shadow-indigo-900/30 p-10 max-w-3xl mx-auto">
          <h2 className="text-3xl font-bold">🔮 Simulate AI-Accelerated Market (2027)</h2>
          <p className="mt-5 text-zinc-300">Current Readiness: 82</p>
          <p className="text-6xl font-extrabold mt-6">{score}</p>
          <p className="text-red-500 font-semibold text-lg mt-4">Δ -19 • Risk Level: HIGH</p>
          <p className="text-zinc-400 mt-6">
            AI skill demand increases 40%
            <br />
            Generic frontend demand decreases 25%
          </p>
        </div>
      </section>

      <section className="panel auditor-stage" id="audit-engine">
        <div className="auditor-header">
          <span className="auditor-icon" aria-hidden>
            *
          </span>
          <div>
            <h2 className="section-title">Skill Gap Closing Auditor</h2>
            <p className="section-subtitle">
              Convert evidence context into concrete skill-gap actions tied to live demand.
            </p>
          </div>
        </div>
        <label className="auditor-label" htmlFor="audit-input">
          Paste Evidence Context
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
              {guideLoading ? "Running Audit..." : "Generate Skill Gap Actions"}
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
