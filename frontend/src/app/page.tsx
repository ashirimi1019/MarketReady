"use client";

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

export default function Home() {
  const { username, isLoggedIn } = useSession();
  const displayName = formatDisplayName(username);
  const headers = useMemo(() => ({ "X-User-Id": username }), [username]);
  const [guide, setGuide] = useState<AiGuide | null>(null);
  const [guideError, setGuideError] = useState<string | null>(null);
  const [guideLoading, setGuideLoading] = useState(false);
  const [proofStats, setProofStats] = useState({
    submitted: 0,
    verified: 0,
    rejected: 0,
  });

  const generateGuide = async () => {
    if (!isLoggedIn) {
      setGuideError("Please log in to generate AI guidance.");
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
        body: JSON.stringify({ question: null }),
      });
      setGuide(data);
    } catch (err) {
      setGuideError(err instanceof Error ? err.message : "AI guide unavailable.");
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
      .catch(() => {
        setProofStats({ submitted: 0, verified: 0, rejected: 0 });
      });
  }, [headers, isLoggedIn]);

  if (isLoggedIn) {
    return (
      <main className="flex flex-col gap-12">
        <section className="panel">
          <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
            <div className="flex flex-col gap-3">
              <span className="badge">Personal Command Center</span>
              <h1 className="text-4xl md:text-5xl font-semibold leading-tight">
                Proof tracker for {displayName}
              </h1>
              <p className="max-w-2xl text-lg text-[color:var(--muted)]">
                You are in control of your readiness. Keep proofs current, track gaps,
                and move each milestone to complete.
              </p>
              <div className="flex flex-wrap gap-3">
                <a className="cta" href="/student/checklist">
                  Submit New Proof
                </a>
                <a className="cta cta-secondary" href="/student/readiness">
                  View Readiness
                </a>
              </div>
            </div>
            <div className="hero-card">
              <div className="flex items-center justify-between">
                <span className="chip">My Progress</span>
                <span className="text-xs text-[color:var(--muted)]">
                  Updated today
                </span>
              </div>
              <div className="mt-6 grid gap-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-[color:var(--muted)]">Next Focus</p>
                    <p className="stat">Checklist Proofs</p>
                  </div>
                  <span className="chip">Active</span>
                </div>
                <div className="kpi-grid">
                  <div className="kpi-cell">
                    <p className="text-xs text-[color:var(--muted)]">Submitted</p>
                    <p className="mt-1 text-2xl font-semibold">{proofStats.submitted}</p>
                  </div>
                  <div className="kpi-cell">
                    <p className="text-xs text-[color:var(--muted)]">Verified</p>
                    <p className="mt-1 text-2xl font-semibold">{proofStats.verified}</p>
                  </div>
                  <div className="kpi-cell">
                    <p className="text-xs text-[color:var(--muted)]">Rejected</p>
                    <p className="mt-1 text-2xl font-semibold">{proofStats.rejected}</p>
                  </div>
                </div>
                <div className="metric-strip">
                  <span className="chip">Status board live</span>
                  <span className="chip">AI guidance on demand</span>
                  <span className="chip">Proof queue tracked</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="panel">
          <h3 className="section-title">AI Decision & Recommendations</h3>
          <p className="section-subtitle mt-2">
            Grounded guidance based on your checklist, milestones, and profile.
          </p>
          <div className="mt-4">
            <button className="cta" onClick={generateGuide} disabled={guideLoading}>
              {guideLoading ? "Generating guidance..." : "Generate Guidance"}
            </button>
          </div>
          {!guide && !guideLoading && !guideError && (
            <p className="mt-4 text-sm text-[color:var(--muted)]">
              Guidance is generated only when you click the button.
            </p>
          )}
          {guideLoading && (
            <p className="mt-4 text-sm text-[color:var(--muted)]">
              Generating guidance...
            </p>
          )}
          {guideError && (
            <p className="mt-4 text-sm text-[color:var(--accent-2)]">
              {guideError}
            </p>
          )}
          {guide && !guideLoading && (
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <div className="rounded-xl border border-[color:var(--border)] p-4">
                <p className="text-sm text-[color:var(--muted)]">Decision</p>
                <p className="mt-2 text-lg font-semibold">
                  {guide.decision || "No decision provided."}
                </p>
              </div>
              <div className="rounded-xl border border-[color:var(--border)] p-4">
                <p className="text-sm text-[color:var(--muted)]">
                  Recommendations
                </p>
                <ul className="mt-2 grid gap-2 text-[color:var(--muted)]">
                  {guide.recommendations?.length ? (
                    guide.recommendations.map((item) => <li key={item}>{item}</li>)
                  ) : (
                    <li>No recommendations yet.</li>
                  )}
                </ul>
              </div>
            </div>
          )}
          {guide?.uncertainty && (
            <p className="mt-3 text-sm text-[color:var(--muted)]">
              {guide.uncertainty}
            </p>
          )}
        </section>

        <section className="grid gap-6 md:grid-cols-3">
          <div className="md:col-span-3">
            <h3 className="section-title">Quick Access</h3>
            <p className="section-subtitle mt-2">
              High-impact actions in one place.
            </p>
          </div>
        </section>

        <section className="action-grid">
          {[
            {
              title: "My Pathway",
              text: "Review your major and pathway selection and confirm your cohort.",
              href: "/student/onboarding",
            },
            {
              title: "Proof Uploads",
              text: "Submit evidence for each checklist item and track verification.",
              href: "/student/checklist",
            },
            {
              title: "My Proofs",
              text: "Review proof status and admin feedback in one place.",
              href: "/student/proofs",
            },
            {
              title: "Readiness Score",
              text: "See your score out of 100 and understand cap reasons.",
              href: "/student/readiness",
            },
            {
              title: "AI Guide",
              text: "Get grounded decisions and recommendations from your data.",
              href: "/student/guide",
            },
            {
              title: "Timeline View",
              text: "Keep milestones aligned with the year-by-year plan.",
              href: "/student/timeline",
            },
            {
              title: "Logout",
              text: "Securely end your session on this device.",
              href: "/logout",
            },
          ].map((card) => (
            <a key={card.title} href={card.href} className="action-card">
              <h2 className="text-xl font-semibold">{card.title}</h2>
              <p className="mt-3 text-[color:var(--muted)]">{card.text}</p>
              <div className="mt-4 text-sm text-[color:var(--accent-2)]">
                Open now
              </div>
            </a>
          ))}
        </section>

        <section className="panel">
          <h3 className="section-title">Todays Focus</h3>
          <p className="section-subtitle mt-2">
            Your checklist is the truth source. Add proof or update milestones to
            keep your readiness current.
          </p>
          <div className="mt-4 grid gap-3 text-[color:var(--muted)]">
            <span>Review missing proofs and prioritize non-negotiables.</span>
            <span>Upload links or files to lock in completed evidence.</span>
            <span>Check readiness for updated next actions.</span>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="flex flex-col gap-16">
      <section className="hero">
        <div className="mx-auto flex max-w-4xl flex-col items-center gap-6 text-center">
          <span className="badge">Market-Verified Readiness Platform</span>
          <h1 className="text-4xl md:text-6xl font-semibold leading-tight">
            Build job-ready graduates with evidence, not assumptions.
          </h1>
          <p className="max-w-3xl text-lg md:text-xl text-[color:var(--muted)]">
            Align students to live hiring signals. Every requirement is versioned,
            measurable, and tied to proof.
          </p>
          <p className="max-w-3xl text-base md:text-lg text-[color:var(--muted)]">
            Market Ready gives students a clear year-by-year execution plan, keeps
            progress measurable through proof-backed milestones, and uses AI to
            recommend what to build next so they can graduate with stronger resumes,
            real project evidence, and a higher chance of landing a role quickly.
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            <a className="cta" href="/student/onboarding">
              Enter Student Portal
            </a>
          </div>
          <div className="flex flex-wrap justify-center gap-3">
            {[
              "Computer Science",
              "Computer Information Systems",
              "More Coming Soon",
            ].map((chip) => (
              <span key={chip} className="chip">
                {chip}
              </span>
            ))}
          </div>
        </div>
      </section>

      <section className="action-grid">
        {[
          {
            title: "Non-Negotiables",
            text: "Each pathway defines what must be proven, not just learned.",
          },
          {
            title: "Readiness Scoring",
            text: "Scores are capped when critical proof is missing, with transparent reasons.",
          },
          {
            title: "Versioned Truth",
            text: "Requirements evolve without shifting the goalposts mid-cohort.",
          },
        ].map((card) => (
          <div key={card.title} className="action-card">
            <h2 className="text-xl font-semibold">{card.title}</h2>
            <p className="mt-3 text-[color:var(--muted)]">{card.text}</p>
          </div>
        ))}
      </section>

      <section className="panel">
        <div className="flex flex-col gap-3">
          <span className="badge">About Market Ready</span>
          <h3 className="section-title">What This Platform Does</h3>
          <p className="section-subtitle">
            Market Ready helps students turn career readiness into a measurable plan.
          </p>
        </div>
        <div className="mt-5 grid gap-5 md:grid-cols-2">
          <div className="rounded-xl border border-[color:var(--border)] p-4">
            <p className="text-sm font-medium text-white">Designed For</p>
            <p className="mt-2 text-[color:var(--muted)]">
              Students, advisors, and program teams who want readiness scoring tied
              to real requirements and market signals.
            </p>
          </div>
          <div className="rounded-xl border border-[color:var(--border)] p-4">
            <p className="text-sm font-medium text-white">Services Provided</p>
            <p className="mt-2 text-[color:var(--muted)]">
              Pathway onboarding, checklist tracking, readiness scoring, certificate
              verification, and AI guidance on next priorities.
            </p>
          </div>
          <div className="rounded-xl border border-[color:var(--border)] p-4 md:col-span-2">
            <p className="text-sm font-medium text-white">How It Works</p>
            <p className="mt-2 text-[color:var(--muted)]">
              Students confirm completed checklist items, upload certificates for AI
              authenticity checks, then the system updates readiness and generates
              targeted recommendations for skills and certifications.
            </p>
          </div>
        </div>
      </section>

      <section className="panel" id="student-flow">
        <h3 className="section-title">Student Flow</h3>
        <p className="section-subtitle mt-2">
          Clarity, pacing, and proof - without guesswork.
        </p>
        <div className="mt-4 grid gap-3 text-[color:var(--muted)]">
          <span>Pick a major and pathway</span>
          <span>Track proof-based checklist items</span>
          <span>See readiness and next best actions</span>
        </div>
      </section>
    </main>
  );
}
