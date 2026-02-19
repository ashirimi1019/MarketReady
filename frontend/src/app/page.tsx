"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { apiGet, apiSend } from "@/lib/api";
import { useSession } from "@/lib/session";
import { formatDisplayName } from "@/lib/name";

type AiGuide = {
  decision?: string | null;
  recommendations?: string[];
  next_actions?: string[];
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
  "Software Eng: +15% demand for OpenAI integration skills",
  "Product Design: shift toward spatial computing",
  "Cybersecurity: zero-trust verification is now a must-have",
  "Data Science: demand rising for production ML + analytics engineering",
  "Cloud: AWS architecture + DevOps automation remain high-demand",
];

const QUICK_LINKS = [
  {
    title: "My Pathway",
    text: "Confirm major, pathway, and year-by-year roadmap.",
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
    text: "View your score out of 100 and cap reasons.",
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

export default function Home() {
  const { username, isLoggedIn } = useSession();
  const displayName = formatDisplayName(username);
  const headers = useMemo(() => ({ "X-User-Id": username }), [username]);

  const [auditInput, setAuditInput] = useState("");
  const [guide, setGuide] = useState<AiGuide | null>(null);
  const [guideError, setGuideError] = useState<string | null>(null);
  const [guideLoading, setGuideLoading] = useState(false);

  const [proofStats, setProofStats] = useState({
    submitted: 0,
    verified: 0,
    rejected: 0,
  });
  const [checklistCount, setChecklistCount] = useState<number | null>(null);
  const [readinessScore, setReadinessScore] = useState<number | null>(null);
  const [readinessRank, setReadinessRank] = useState<ReadinessRank | null>(null);
  const [weeklyStreak, setWeeklyStreak] = useState<WeeklyMilestoneStreak | null>(null);

  const runAudit = async () => {
    if (!isLoggedIn) {
      setGuideError("Log in to run the OpenAI audit.");
      return;
    }
    setGuideLoading(true);
    setGuideError(null);
    try {
      const data = await apiSend<AiGuide>("/user/ai/guide", {
        method: "POST",
        headers: {
          ...headers,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ question: auditInput.trim() || null }),
      });
      setGuide(data);
    } catch (err) {
      setGuideError(err instanceof Error ? err.message : "OpenAI audit unavailable.");
    } finally {
      setGuideLoading(false);
    }
  };

  useEffect(() => {
    if (isLoggedIn) return;
    setGuide(null);
    setGuideError(null);
    setGuideLoading(false);
  }, [isLoggedIn]);

  useEffect(() => {
    if (!isLoggedIn) return;
    apiGet<Proof[]>("/user/proofs", headers)
      .then((proofs) => {
        const stats = { submitted: 0, verified: 0, rejected: 0 };
        proofs.forEach((proof) => {
          if (proof.status === "verified") stats.verified += 1;
          else if (proof.status === "rejected") stats.rejected += 1;
          else stats.submitted += 1;
        });
        setProofStats(stats);
      })
      .catch(() => setProofStats({ submitted: 0, verified: 0, rejected: 0 }));
  }, [headers, isLoggedIn]);

  useEffect(() => {
    if (!isLoggedIn) return;
    apiGet<ChecklistItem[]>("/user/checklist", headers)
      .then((items) => setChecklistCount(items.length))
      .catch(() => setChecklistCount(null));
  }, [headers, isLoggedIn]);

  useEffect(() => {
    if (!isLoggedIn) return;
    apiGet<Readiness>("/user/readiness", headers)
      .then((readiness) => setReadinessScore(readiness.score))
      .catch(() => setReadinessScore(null));
  }, [headers, isLoggedIn]);

  useEffect(() => {
    if (!isLoggedIn) return;
    apiGet<ReadinessRank>("/user/readiness/rank", headers)
      .then(setReadinessRank)
      .catch(() => setReadinessRank(null));
  }, [headers, isLoggedIn]);

  useEffect(() => {
    if (!isLoggedIn) return;
    apiGet<WeeklyMilestoneStreak>("/user/streak", headers)
      .then(setWeeklyStreak)
      .catch(() => setWeeklyStreak(null));
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
        <span className="hero-signal-pill">
          AI-Powered Verification Engine · Powered by OpenAI
        </span>
        <h1 className="hero-headline">
          Stop <span className="hero-emphasis">guessing.</span>
          <br />
          Start proving.
        </h1>
        <p className="hero-copy">
          {isLoggedIn
            ? `${displayName}, your roadmap is now evidence-driven. Audit progress, close high-impact gaps, and keep your proof vault market-ready.`
            : "The platform that converts career progress into verifiable outcomes using live hiring signals, OpenAI-powered guidance, and proof-backed milestones."}
        </p>
        {isLoggedIn && (
          <p className="mt-3 text-sm text-[color:var(--muted)]">
            Weekly proof streak: {weeklyStreak?.current_streak_weeks ?? 0} week(s)
          </p>
        )}
        <div className="hero-actions">
          {isLoggedIn ? (
            <>
              <Link href="/student/checklist" className="cta">
                Open Proof Workflow
              </Link>
              <Link href="/student/readiness" className="cta cta-secondary">
                View Readiness
              </Link>
            </>
          ) : (
            <>
              <Link href="/register" className="cta">
                Enter Student Portal
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
            ✦
          </span>
          <div>
            <h2 className="section-title">AI Market Auditor · Powered by OpenAI</h2>
            <p className="section-subtitle">
              Paste resume highlights or project evidence and generate OpenAI-powered direction.
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
          placeholder="Ex: Built and deployed a full-stack app with React, FastAPI, PostgreSQL, Docker, and AWS."
        />
        <div className="auditor-actions">
          {isLoggedIn ? (
            <button className="cta auditor-cta" onClick={runAudit} disabled={guideLoading}>
              {guideLoading ? "Running Audit..." : "Audit My Readiness"}
            </button>
          ) : (
            <Link className="cta auditor-cta" href="/login">
              Audit My Readiness
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
          </div>
        )}

        {guide?.uncertainty && (
          <p className="auditor-feedback">{guide.uncertainty}</p>
        )}
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
          <p className="mt-4 text-sm text-[color:var(--muted)]">
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
