"use client";

import { useEffect, useMemo, useState, useRef } from "react";
import { apiGet, apiSend } from "@/lib/api";
import { useSession } from "@/lib/session";

type MRIData = {
  score: number;
  components: { federal_standards: number; market_demand: number; evidence_density: number };
  weights: { federal_standards: number; market_demand: number; evidence_density: number };
  gaps: string[];
  recommendations: string[];
  band: string;
  formula: string;
  proficiency_breakdown?: { beginner: number; intermediate: number; professional: number };
  ai_verified_certs?: number;
};

type GitHubAudit = {
  username: string;
  verified_skills: string[];
  commit_skill_signals: string[];
  velocity: { velocity_score: number; recent_repos: number; total_repos: number; languages: string[]; stars: number };
  warnings: string[];
  bulk_upload_detected: boolean;
};

type SimulatorResult = {
  acceleration: number;
  adjusted_score: number;
  original_score: number;
  delta: number;
  skill_profiles: { skill: string; multiplier: number; classification: string; verified: boolean }[];
  risk_level: string;
  recommendations: string[];
};

type StudentProfile = { github_username?: string | null };

function AnimatedScore({ target, size = "lg" }: { target: number; size?: "sm" | "lg" }) {
  const [current, setCurrent] = useState(0);
  useEffect(() => {
    const steps = 40;
    const inc = target / steps;
    let step = 0;
    const timer = setInterval(() => {
      step++;
      setCurrent(Math.min(Math.round(inc * step), target));
      if (step >= steps) clearInterval(timer);
    }, 25);
    return () => clearInterval(timer);
  }, [target]);

  const radius = size === "lg" ? 54 : 36;
  const stroke = size === "lg" ? 7 : 5;
  const circ = 2 * Math.PI * radius;
  const pct = Math.min(current / 100, 1);
  const offset = circ * (1 - pct);
  const color = target >= 85 ? "#00c896" : target >= 65 ? "#3d6dff" : target >= 45 ? "#ffb300" : "#ff3b30";

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width={radius * 2 + stroke * 2 + 4} height={radius * 2 + stroke * 2 + 4} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={radius + stroke / 2 + 2} cy={radius + stroke / 2 + 2} r={radius} fill="none" stroke="rgba(61,109,255,0.12)" strokeWidth={stroke} />
        <circle cx={radius + stroke / 2 + 2} cy={radius + stroke / 2 + 2} r={radius} fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={circ} strokeDashoffset={offset} style={{ transition: "stroke-dashoffset 0.05s linear" }} />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className={size === "lg" ? "text-3xl font-bold" : "text-xl font-bold"} style={{ color }}>{current}</span>
        <span className="text-xs text-[color:var(--muted)]">/ 100</span>
      </div>
    </div>
  );
}

function SegmentBar({ label, value, weight, color }: { label: string; value: number; weight: number; color: string }) {
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between items-center text-sm">
        <span className="text-[color:var(--muted)]">{label}</span>
        <span className="font-semibold" style={{ color }}>{value.toFixed(0)}</span>
      </div>
      <div className="h-2 rounded-full bg-[rgba(61,109,255,0.1)] overflow-hidden">
        <div className="h-full rounded-full transition-all duration-700" style={{ width: `${value}%`, background: color }} />
      </div>
      <div className="text-xs text-[color:var(--muted)]">Weight: {(weight * 100).toFixed(0)}%</div>
    </div>
  );
}

export default function StudentReadinessPage() {
  const { username, isLoggedIn } = useSession();
  const headers = useMemo(() => ({}), []);
  const [mri, setMri] = useState<MRIData | null>(null);
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [audit, setAudit] = useState<GitHubAudit | null>(null);
  const [auditLoading, setAuditLoading] = useState(false);
  const [simResult, setSimResult] = useState<SimulatorResult | null>(null);
  const [acceleration, setAcceleration] = useState(50);
  const [simLoading, setSimLoading] = useState(false);
  const simTimer = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (!isLoggedIn) return;
    apiGet<MRIData>("/score/mri").then(setMri).catch(() => setMri(null));
    apiGet<StudentProfile>("/user/profile").then(setProfile).catch(() => setProfile(null));
  }, [isLoggedIn]);

  // Run audit when profile with github loaded
  useEffect(() => {
    if (!isLoggedIn || !profile?.github_username) return;
    setAuditLoading(true);
    fetch(`${process.env.NEXT_PUBLIC_API_BASE}/github/audit/${profile.github_username}`)
      .then(r => r.json()).then(setAudit).catch(() => setAudit(null)).finally(() => setAuditLoading(false));
  }, [profile, isLoggedIn]);

  // Debounced simulator
  useEffect(() => {
    if (!isLoggedIn) return;
    if (simTimer.current) clearTimeout(simTimer.current);
    simTimer.current = setTimeout(() => {
      setSimLoading(true);
      apiSend<SimulatorResult>("/simulator/future-shock", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ acceleration }),
      }).then(setSimResult).catch(() => setSimResult(null)).finally(() => setSimLoading(false));
    }, 400);
    return () => { if (simTimer.current) clearTimeout(simTimer.current); };
  }, [acceleration, isLoggedIn]);

  const bandColor = (band: string) => {
    if (band === "Market Ready") return "#00c896";
    if (band === "Competitive") return "#3d6dff";
    if (band === "Developing") return "#ffb300";
    return "#ff3b30";
  };

  return (
    <section className="panel space-y-8">
      <div>
        <h2 className="text-3xl font-bold tracking-tight" data-testid="mri-title">MRI Score</h2>
        <p className="mt-1 text-[color:var(--muted)] text-sm">Market-Ready Index — your career readiness measured by what employers verify</p>
      </div>

      {!isLoggedIn && (
        <div className="rounded-2xl border border-[color:var(--border)] p-6 text-center">
          <p className="text-[color:var(--muted)]">Please log in to view your MRI score.</p>
        </div>
      )}

      {isLoggedIn && (
        <>
          {/* MRI Score Hero */}
          <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)] p-6" data-testid="mri-score-card">
            <div className="flex flex-col md:flex-row gap-8 items-center">
              <div className="flex flex-col items-center gap-2">
                <AnimatedScore target={mri?.score ?? 0} size="lg" />
                <span className="text-sm font-semibold px-3 py-1 rounded-full" style={{ background: mri ? `${bandColor(mri.band)}22` : undefined, color: mri ? bandColor(mri.band) : "var(--muted)" }}>
                  {mri?.band ?? "Loading..."}
                </span>
              </div>
              <div className="flex-1 space-y-4 w-full">
                <p className="text-xs text-[color:var(--muted)] font-mono mb-3">{mri?.formula}</p>
                <SegmentBar label="Federal Standards (O*NET)" value={mri?.components.federal_standards ?? 0} weight={mri?.weights.federal_standards ?? 0.4} color="#3d6dff" />
                <SegmentBar label="Market Demand (Adzuna)" value={mri?.components.market_demand ?? 0} weight={mri?.weights.market_demand ?? 0.3} color="#00c896" />
                <SegmentBar label="Evidence Density" value={mri?.components.evidence_density ?? 0} weight={mri?.weights.evidence_density ?? 0.3} color="#ff7b1a" />
              </div>
            </div>

            {/* Proficiency breakdown */}
            {mri && (
              <div className="mt-4 pt-4 border-t border-[color:var(--border)]">
                <div className="flex flex-wrap gap-4 items-center">
                  <p className="text-xs text-[color:var(--muted)] font-semibold">Proficiency Mix</p>
                  {[
                    { label: "Beginner (50%)", value: mri.proficiency_breakdown?.beginner ?? 0, color: "#ffb300" },
                    { label: "Intermediate (75%)", value: mri.proficiency_breakdown?.intermediate ?? 0, color: "#3d6dff" },
                    { label: "Professional (100%)", value: mri.proficiency_breakdown?.professional ?? 0, color: "#00c896" },
                  ].map(({ label, value, color }) => (
                    <div key={label} className="flex items-center gap-1.5">
                      <span className="h-2 w-2 rounded-full" style={{ background: color }} />
                      <span className="text-xs" style={{ color }}>{value} {label}</span>
                    </div>
                  ))}
                  {(mri.ai_verified_certs ?? 0) > 0 && (
                    <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "rgba(0,200,150,0.1)", color: "#00c896" }}>
                      {mri.ai_verified_certs} AI-verified cert{(mri.ai_verified_certs ?? 0) > 1 ? "s" : ""}
                    </span>
                  )}
                </div>
                <a href="/student/checklist" className="mt-2 inline-block text-xs text-[color:var(--primary)] hover:opacity-80">
                  Boost score by upgrading to Professional proficiency →
                </a>
              </div>
            )}
          </div>

          {/* What's Dragging Your Score */}
          {mri && (mri.gaps.length > 0 || mri.recommendations.length > 0) && (
            <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)] p-6" data-testid="mri-gaps-card">
              <h3 className="text-lg font-semibold mb-4">What's Dragging Your Score</h3>
              <div className="grid md:grid-cols-2 gap-4">
                {mri.gaps.length > 0 && (
                  <div>
                    <p className="text-sm text-[color:var(--muted)] mb-2">Top Gaps</p>
                    <ul className="space-y-1.5">
                      {mri.gaps.map(gap => (
                        <li key={gap} className="flex items-start gap-2 text-sm">
                          <span className="mt-1 h-1.5 w-1.5 rounded-full bg-[color:var(--danger)] flex-shrink-0" />
                          <a href="/student/checklist" className="text-[color:var(--muted)] hover:text-[color:var(--foreground)] transition-colors">{gap}</a>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                <div>
                  <p className="text-sm text-[color:var(--muted)] mb-2">Actionable Next Steps</p>
                  <ul className="space-y-1.5">
                    {mri.recommendations.map(rec => (
                      <li key={rec} className="flex items-start gap-2 text-sm">
                        <span className="mt-1 h-1.5 w-1.5 rounded-full bg-[color:var(--primary)] flex-shrink-0" />
                        <span className="text-[color:var(--muted)]">{rec}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}

          {/* GitHub Signal Auditor */}
          <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)] p-6" data-testid="github-audit-card">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">GitHub Signal Auditor</h3>
              {audit && (
                <span className="text-xs px-2 py-1 rounded-full bg-[rgba(0,200,150,0.1)] text-[color:var(--success)]">
                  @{audit.username}
                </span>
              )}
            </div>
            {!profile?.github_username ? (
              <div className="text-center py-4">
                <p className="text-sm text-[color:var(--muted)] mb-3">Connect your GitHub to verify skills automatically</p>
                <a href="/student/profile" className="cta cta-secondary text-sm">Add GitHub Username</a>
              </div>
            ) : auditLoading ? (
              <div className="flex items-center gap-3 text-sm text-[color:var(--muted)]">
                <div className="h-4 w-4 rounded-full border-2 border-[color:var(--primary)] border-t-transparent animate-spin" />
                Analyzing GitHub repos...
              </div>
            ) : audit ? (
              <div className="space-y-4">
                {audit.warnings.length > 0 && (
                  <div className="rounded-lg bg-[rgba(255,179,0,0.08)] border border-[rgba(255,179,0,0.2)] p-3 text-sm text-[color:var(--warning)]">
                    {audit.warnings.map(w => <p key={w}>{w}</p>)}
                  </div>
                )}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {[
                    { label: "Velocity", value: `${audit.velocity.velocity_score}/100` },
                    { label: "Recent Repos", value: audit.velocity.recent_repos },
                    { label: "Stars", value: audit.velocity.stars.toLocaleString() },
                    { label: "Languages", value: audit.velocity.languages.length },
                  ].map(({ label, value }) => (
                    <div key={label} className="rounded-xl border border-[color:var(--border)] p-3 text-center">
                      <p className="text-xs text-[color:var(--muted)]">{label}</p>
                      <p className="text-lg font-bold mt-1">{value}</p>
                    </div>
                  ))}
                </div>
                <div className="grid md:grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs text-[color:var(--muted)] mb-2">Verified Skills (from deps)</p>
                    <div className="flex flex-wrap gap-1.5">
                      {audit.verified_skills.slice(0, 10).map(s => (
                        <span key={s} className="px-2 py-0.5 rounded-full text-xs bg-[rgba(0,200,150,0.1)] text-[color:var(--success)] border border-[rgba(0,200,150,0.2)]">{s}</span>
                      ))}
                      {audit.verified_skills.length === 0 && <span className="text-xs text-[color:var(--muted)]">No skills detected yet</span>}
                    </div>
                  </div>
                  <div>
                    <p className="text-xs text-[color:var(--muted)] mb-2">Commit Signals</p>
                    <div className="flex flex-wrap gap-1.5">
                      {audit.commit_skill_signals.slice(0, 8).map(s => (
                        <span key={s} className="px-2 py-0.5 rounded-full text-xs bg-[rgba(61,109,255,0.1)] text-[color:var(--primary)] border border-[rgba(61,109,255,0.2)]">{s}</span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-sm text-[color:var(--muted)]">Could not load GitHub data</p>
            )}
          </div>

          {/* 2027 Future-Shock Simulator */}
          <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)] p-6" data-testid="future-shock-card">
            <h3 className="text-lg font-semibold mb-1">2027 Future-Shock Simulator</h3>
            <p className="text-xs text-[color:var(--muted)] mb-5">Drag to simulate how AI acceleration impacts your skill portfolio</p>

            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-sm text-[color:var(--muted)]">AI Acceleration</span>
                <span className="text-sm font-bold" style={{ color: acceleration > 70 ? "#ff3b30" : acceleration > 40 ? "#ffb300" : "#00c896" }}>
                  {acceleration}%
                </span>
              </div>
              <input
                type="range" min={0} max={100} value={acceleration}
                onChange={e => setAcceleration(Number(e.target.value))}
                className="w-full accent-[color:var(--primary)] cursor-pointer"
                data-testid="acceleration-slider"
              />
              <div className="flex justify-between text-xs text-[color:var(--muted)]">
                <span>Stable (0%)</span><span>Disruption (50%)</span><span>Shock (100%)</span>
              </div>
            </div>

            {simLoading && <div className="mt-4 text-sm text-[color:var(--muted)] animate-pulse">Calculating...</div>}

            {simResult && !simLoading && (
              <div className="mt-5 space-y-4">
                <div className="grid grid-cols-3 gap-3">
                  <div className="rounded-xl border border-[color:var(--border)] p-3 text-center">
                    <p className="text-xs text-[color:var(--muted)]">Projected Score</p>
                    <p className="text-2xl font-bold mt-1">{simResult.adjusted_score}</p>
                  </div>
                  <div className="rounded-xl border border-[color:var(--border)] p-3 text-center">
                    <p className="text-xs text-[color:var(--muted)]">Delta</p>
                    <p className="text-2xl font-bold mt-1" style={{ color: simResult.delta >= 0 ? "#00c896" : "#ff3b30" }}>
                      {simResult.delta >= 0 ? "+" : ""}{simResult.delta}
                    </p>
                  </div>
                  <div className="rounded-xl border border-[color:var(--border)] p-3 text-center">
                    <p className="text-xs text-[color:var(--muted)]">Risk Level</p>
                    <p className="text-lg font-bold mt-1 capitalize" style={{ color: simResult.risk_level === "high" ? "#ff3b30" : simResult.risk_level === "medium" ? "#ffb300" : "#00c896" }}>
                      {simResult.risk_level}
                    </p>
                  </div>
                </div>

                {simResult.skill_profiles.length > 0 && (
                  <div>
                    <p className="text-sm text-[color:var(--muted)] mb-2">Skill Risk Profile</p>
                    <div className="grid grid-cols-2 gap-2">
                      {simResult.skill_profiles.slice(0, 6).map(s => (
                        <div key={s.skill} className="flex items-center gap-2 text-xs rounded-lg p-2"
                          style={{ background: s.classification === "resilient" ? "rgba(0,200,150,0.08)" : "rgba(255,59,48,0.08)" }}>
                          <span className="h-2 w-2 rounded-full flex-shrink-0"
                            style={{ background: s.classification === "resilient" ? "#00c896" : "#ff3b30" }} />
                          <span className="truncate text-[color:var(--muted)]">{s.skill}</span>
                          <span className="ml-auto font-mono text-[10px]">{s.multiplier.toFixed(1)}x</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {simResult.recommendations.length > 0 && (
                  <div className="rounded-xl bg-[rgba(61,109,255,0.06)] border border-[rgba(61,109,255,0.15)] p-3">
                    <p className="text-xs font-semibold text-[color:var(--primary)] mb-2">Recommended Pivots</p>
                    {simResult.recommendations.map(r => (
                      <p key={r} className="text-xs text-[color:var(--muted)] mb-1">{r}</p>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </>
      )}
    </section>
  );
}
