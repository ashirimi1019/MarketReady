"use client";

import { useEffect, useMemo, useState } from "react";
import { apiGet, apiSend } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { useSession } from "@/lib/session";
import type { AICareerOrchestrator, MarketStressTest, RepoProofChecker, StudentProfile } from "@/types/api";

const STRATEGIC_TIPS = [
  "Ship one public proof artifact every week, then rerun GitHub Proof Auditor.",
  "When MRI trend cools down, prioritize transferable backend/cloud/security projects.",
  "Treat missing skills as sprint tickets: one skill, one repo proof, one verified check.",
  "Use local-demand signals to choose projects, not random tutorial paths.",
];

type KanbanLane = "backlog" | "in_progress" | "done";

type MissionTask = {
  id: string;
  label: string;
  phase: string;
  lane: KanbanLane;
};

function trendLabel(value: string): string {
  if (value === "heating_up") return "Heating Up";
  if (value === "cooling_down") return "Cooling Down";
  return "Neutral";
}

function mriTheme(score: number) {
  if (score >= 75) {
    return {
      label: "Market Ready",
      tone: "text-emerald-400",
      border: "border-emerald-500/40",
      glow: "shadow-[0_0_25px_rgba(16,185,129,0.25)]",
      ringHex: "#10b981",
      bg: "from-zinc-900 via-zinc-950 to-emerald-950/40",
    };
  }
  if (score >= 55) {
    return {
      label: "Watchlist",
      tone: "text-amber-400",
      border: "border-amber-500/40",
      glow: "shadow-[0_0_25px_rgba(245,158,11,0.2)]",
      ringHex: "#f59e0b",
      bg: "from-zinc-900 via-zinc-950 to-amber-950/30",
    };
  }
  return {
    label: "High Risk",
    tone: "text-red-400",
    border: "border-red-500/40",
    glow: "shadow-[0_0_25px_rgba(239,68,68,0.25)]",
    ringHex: "#ef4444",
    bg: "from-zinc-900 via-zinc-950 to-red-950/35",
  };
}

async function reverseGeocode(lat: number, lon: number): Promise<string | null> {
  try {
    const response = await fetch(
      `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${lat}&lon=${lon}`,
      { headers: { Accept: "application/json" } }
    );
    if (!response.ok) return null;
    const payload = (await response.json()) as {
      address?: { city?: string; town?: string; village?: string; state?: string; country?: string };
    };
    const city = payload.address?.city || payload.address?.town || payload.address?.village;
    const state = payload.address?.state;
    const country = payload.address?.country;
    if (city && state) return `${city}, ${state}`;
    if (state && country) return `${state}, ${country}`;
    if (country) return country;
    return null;
  } catch {
    return null;
  }
}

export default function StudentAiGuidePage() {
  const { username, isLoggedIn } = useSession();
  const headers = useMemo(() => ({ "X-User-Id": username }), [username]);

  const [targetJob, setTargetJob] = useState("software engineer");
  const [location, setLocation] = useState("united states");
  const [availabilityHours, setAvailabilityHours] = useState("20");
  const [repoUrl, setRepoUrl] = useState("");
  const [smartSyncNotes, setSmartSyncNotes] = useState<string[]>([]);
  const [profile, setProfile] = useState<StudentProfile | null>(null);

  const [stressResult, setStressResult] = useState<MarketStressTest | null>(null);
  const [stressLoading, setStressLoading] = useState(false);
  const [stressError, setStressError] = useState<string | null>(null);

  const [repoResult, setRepoResult] = useState<RepoProofChecker | null>(null);
  const [repoLoading, setRepoLoading] = useState(false);
  const [repoError, setRepoError] = useState<string | null>(null);

  const [orchestratorResult, setOrchestratorResult] = useState<AICareerOrchestrator | null>(null);
  const [orchestratorLoading, setOrchestratorLoading] = useState(false);
  const [orchestratorError, setOrchestratorError] = useState<string | null>(null);
  const [pivotLoading, setPivotLoading] = useState(false);
  const [pivotError, setPivotError] = useState<string | null>(null);
  const [weeklyChecks, setWeeklyChecks] = useState<Record<string, boolean>>({});
  const [kanbanTasks, setKanbanTasks] = useState<MissionTask[]>([]);
  const [tipSeed, setTipSeed] = useState(0);

  const [futureYear, setFutureYear] = useState(2026);

  useEffect(() => {
    if (!isLoggedIn) return;

    let cancelled = false;
    const notes: string[] = [];

    apiGet<StudentProfile>("/user/profile", headers)
      .then((profilePayload) => {
        if (cancelled) return;
        setProfile(profilePayload);
        if (profilePayload.state) {
          setLocation(profilePayload.state);
          notes.push(`Location from profile: ${profilePayload.state}`);
        }
        if (profilePayload.github_username) {
          setRepoUrl(`https://github.com/${profilePayload.github_username}`);
          notes.push(`GitHub synced: @${profilePayload.github_username}`);
          fetch(`https://api.github.com/users/${profilePayload.github_username}`)
            .then(async (response) => {
              if (!response.ok) return null;
              const payload = (await response.json()) as { location?: string | null; bio?: string | null };
              return payload;
            })
            .then((githubProfile) => {
              if (!githubProfile || cancelled) return;
              if (githubProfile.location && !profilePayload.state) {
                setLocation(githubProfile.location);
                setSmartSyncNotes((prev) => Array.from(new Set([...prev, `Location from GitHub: ${githubProfile.location}`])));
              }
              const bio = (githubProfile.bio || "").toLowerCase();
              if (bio.includes("backend")) setTargetJob("backend engineer");
              else if (bio.includes("security")) setTargetJob("cybersecurity analyst");
              else if (bio.includes("data")) setTargetJob("data engineer");
            })
            .catch(() => null);
        }
        if (profilePayload.resume_filename) {
          notes.push(`Resume synced: ${profilePayload.resume_filename}`);
        }
        setSmartSyncNotes((prev) => Array.from(new Set([...prev, ...notes])));
      })
      .catch(() => null);

    if ("geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition(
        async (position) => {
          if (cancelled) return;
          const resolved = await reverseGeocode(position.coords.latitude, position.coords.longitude);
          if (resolved) {
            setLocation(resolved);
            setSmartSyncNotes((prev) => Array.from(new Set([...prev, `Location from browser: ${resolved}`])));
          }
        },
        () => null,
        { timeout: 3000 }
      );
    }

    return () => {
      cancelled = true;
    };
  }, [headers, isLoggedIn]);

  useEffect(() => {
    setTipSeed(Math.floor(Math.random() * STRATEGIC_TIPS.length));
  }, []);

  const runStressTest = async () => {
    if (!isLoggedIn) {
      setStressError("Please log in to run MRI.");
      return;
    }
    setStressLoading(true);
    setStressError(null);
    try {
      const data = await apiSend<MarketStressTest>("/user/ai/market-stress-test", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({
          target_job: targetJob.trim() || "software engineer",
          location: location.trim() || "united states",
        }),
      });
      setStressResult(data);
    } catch (err) {
      setStressError(getErrorMessage(err) || "Market stress test unavailable.");
      setStressResult(null);
    } finally {
      setStressLoading(false);
    }
  };

  const runRepoAudit = async () => {
    if (!isLoggedIn) {
      setRepoError("Please log in to verify by GitHub.");
      return;
    }
    setRepoLoading(true);
    setRepoError(null);
    try {
      const data = await apiSend<RepoProofChecker>("/user/ai/proof-checker", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({
          target_job: targetJob.trim() || "software engineer",
          location: location.trim() || "united states",
          repo_url: repoUrl.trim(),
        }),
      });
      setRepoResult(data);
    } catch (err) {
      setRepoError(getErrorMessage(err) || "GitHub proof auditor unavailable.");
      setRepoResult(null);
    } finally {
      setRepoLoading(false);
    }
  };

  const runOrchestrator = async (pivotRequested = false) => {
    if (!isLoggedIn) {
      setOrchestratorError("Please log in to run the mission planner.");
      return;
    }
    if (pivotRequested) {
      setPivotLoading(true);
    } else {
      setOrchestratorLoading(true);
    }
    setOrchestratorError(null);
    setPivotError(null);

    try {
      const parsedHours = Number(availabilityHours);
      const payload = await apiSend<AICareerOrchestrator>("/user/ai/orchestrator", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({
          target_job: targetJob.trim() || "software engineer",
          location: location.trim() || "united states",
          availability_hours_per_week: Number.isFinite(parsedHours) ? parsedHours : 20,
          pivot_requested: pivotRequested,
        }),
      });
      setOrchestratorResult(payload);
    } catch (err) {
      const message = getErrorMessage(err) || "Mission planner unavailable.";
      if (pivotRequested) {
        setPivotError(message);
      } else {
        setOrchestratorError(message);
      }
      setOrchestratorResult(null);
    } finally {
      if (pivotRequested) {
        setPivotLoading(false);
      } else {
        setOrchestratorLoading(false);
      }
    }
  };

  const mriScore = stressResult?.score ?? 0;
  const mri = mriTheme(mriScore);
  const gaugePct = Math.max(0, Math.min(100, mriScore));
  const simulation = stressResult?.simulation_2027 ?? null;
  const projectedScore = futureYear === 2027 && simulation ? simulation.projected_score : mriScore;
  const projectedDelta = futureYear === 2027 && simulation ? simulation.delta : 0;
  const projectedRisk = futureYear === 2027 && simulation ? simulation.risk_level : "baseline";

  const mission = useMemo(
    () => ((orchestratorResult?.mission_dashboard as Record<string, unknown>) || {}),
    [orchestratorResult]
  );
  const day0 = useMemo(() => (Array.isArray(mission.day_0_30) ? (mission.day_0_30 as string[]) : []), [mission]);
  const day31 = useMemo(() => (Array.isArray(mission.day_31_60) ? (mission.day_31_60 as string[]) : []), [mission]);
  const day61 = useMemo(() => (Array.isArray(mission.day_61_90) ? (mission.day_61_90 as string[]) : []), [mission]);
  const weekly = useMemo(
    () => (Array.isArray(mission.weekly_checkboxes) ? (mission.weekly_checkboxes as string[]) : []),
    [mission]
  );
  const weeklyCompleted = weekly.filter((item) => weeklyChecks[item]).length;
  const weeklyProgressPct = weekly.length ? Math.round((weeklyCompleted / weekly.length) * 100) : 0;
  const kanbanDoneCount = kanbanTasks.filter((task) => task.lane === "done").length;
  const kanbanProgressPct = kanbanTasks.length ? Math.round((kanbanDoneCount / kanbanTasks.length) * 100) : 0;
  const salaryFormatter = useMemo(
    () =>
      new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 0,
      }),
    []
  );
  const volatilityMax = useMemo(
    () =>
      Math.max(
        1,
        ...(stressResult?.market_volatility_points?.map((point) => point.y).filter((value) => Number.isFinite(value)) || [1])
      ),
    [stressResult]
  );

  useEffect(() => {
    setWeeklyChecks((prev) => {
      const next: Record<string, boolean> = {};
      for (const item of weekly) {
        next[item] = prev[item] ?? false;
      }
      return next;
    });
  }, [weekly]);

  useEffect(() => {
    const baseTasks: MissionTask[] = [
      ...day0.map((label, index) => ({
        id: `d0-${index}-${label}`,
        label,
        phase: "Day 0-30",
        lane: "backlog" as const,
      })),
      ...day31.map((label, index) => ({
        id: `d31-${index}-${label}`,
        label,
        phase: "Day 31-60",
        lane: "backlog" as const,
      })),
      ...day61.map((label, index) => ({
        id: `d61-${index}-${label}`,
        label,
        phase: "Day 61-90",
        lane: "backlog" as const,
      })),
    ];

    setKanbanTasks((prev) => {
      const laneById = new Map(prev.map((task) => [task.id, task.lane]));
      return baseTasks.map((task) => ({
        ...task,
        lane: laneById.get(task.id) || "backlog",
      }));
    });
  }, [day0, day31, day61]);

  const strategicTip = useMemo(() => {
    const topMissingSkill = stressResult?.missing_skills?.[0];
    if (topMissingSkill) {
      return `Skill-gap move: build one public repo artifact for "${topMissingSkill}" and rerun Proof Auditor.`;
    }
    const repoGap = repoResult?.skills_required_but_missing?.[0];
    if (repoGap) {
      return `Code evidence move: close "${repoGap}" this week with one deployed project update.`;
    }
    return STRATEGIC_TIPS[tipSeed % STRATEGIC_TIPS.length];
  }, [repoResult, stressResult, tipSeed]);

  const exportMissionPlan = () => {
    if (!orchestratorResult) return;

    const today = new Date().toISOString().slice(0, 10);
    const slug = (targetJob.trim() || "career-mission").toLowerCase().replace(/[^a-z0-9]+/g, "-");
    const lines = [
      "Market Ready - 90-Day Agentic Mission",
      `Generated: ${today}`,
      `Target Role: ${targetJob}`,
      `Location: ${location}`,
      "",
      `Market Alert: ${orchestratorResult.market_alert || "n/a"}`,
      "",
      "Day 0-30",
      ...day0.map((item) => `- ${item}`),
      "",
      "Day 31-60",
      ...day31.map((item) => `- ${item}`),
      "",
      "Day 61-90",
      ...day61.map((item) => `- ${item}`),
      "",
      "Weekly Checklist",
      ...weekly.map((item) => `- [${weeklyChecks[item] ? "x" : " "}] ${item}`),
      "",
      "Interactive Kanban Status",
      ...kanbanTasks.map((task) => `- [${task.lane}] ${task.label} (${task.phase})`),
      "",
      `Progress: ${weeklyCompleted}/${weekly.length || 0} (${weeklyProgressPct}%)`,
    ];

    const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${slug}-90-day-mission-${today}.txt`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  const moveKanbanTask = (taskId: string, lane: KanbanLane) => {
    setKanbanTasks((prev) =>
      prev.map((task) => (task.id === taskId ? { ...task, lane } : task))
    );
  };

  return (
    <section className="panel space-y-6">
      <h2 className="text-3xl font-semibold">AI Career Services</h2>
      <p className="text-[color:var(--muted)]">
        Data-driven workflow: MRI score + GitHub validation + market-weighted mission planning.
      </p>

      {!isLoggedIn && (
        <p className="text-sm text-[color:var(--accent-2)]">
          Please log in to use Market Stress Test, GitHub Proof Auditor, and the agentic mission workflow.
        </p>
      )}

      <div className="rounded-xl border border-[color:var(--border)] p-5">
        <h3 className="text-xl font-semibold">Smart Sync</h3>
        <p className="mt-1 text-sm text-[color:var(--muted)]">
          Defaults are pulled from profile, browser location, and GitHub profile when available.
        </p>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <input
            className="rounded-lg border border-[color:var(--border)] p-3"
            value={targetJob}
            onChange={(e) => setTargetJob(e.target.value)}
            placeholder="Target job"
          />
          <input
            className="rounded-lg border border-[color:var(--border)] p-3"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="Location"
          />
          <input
            className="rounded-lg border border-[color:var(--border)] p-3"
            type="number"
            min={1}
            max={80}
            value={availabilityHours}
            onChange={(e) => setAvailabilityHours(e.target.value)}
            placeholder="Hours/week"
          />
        </div>
        {smartSyncNotes.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {smartSyncNotes.map((note) => (
              <span key={note} className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-zinc-300">
                {note}
              </span>
            ))}
          </div>
        )}
        {profile?.university && <p className="mt-3 text-xs text-[color:var(--muted)]">Education context: {profile.university}</p>}
      </div>

      <div className="rounded-xl border border-[color:var(--border)] p-5">
        <h3 className="text-xl font-semibold">Market-Ready Index (MRI) Stress Test</h3>
        <p className="mt-1 text-sm text-[color:var(--muted)]">
          We do not guess. MRI weights federal skill standards against live local demand and verified proof density.
        </p>
        <div className="mt-4">
          <button className="cta" onClick={runStressTest} disabled={!isLoggedIn || stressLoading}>
            {stressLoading ? "Running..." : "Run Market Stress Test"}
          </button>
        </div>

        {stressError && (
          <div className="mt-3 rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">
            {stressError}
          </div>
        )}

        {stressResult && (
          <div className="mt-4 space-y-4">
            <div className={`rounded-2xl border bg-gradient-to-br p-5 ${mri.border} ${mri.glow} ${mri.bg}`}>
              <div className="grid gap-6 md:grid-cols-[220px_1fr]">
                <div className="mx-auto flex w-full max-w-[220px] flex-col items-center">
                  <div
                    className="relative h-44 w-44 rounded-full"
                    style={{
                      background: `conic-gradient(${mri.ringHex} ${gaugePct}%, rgba(255,255,255,0.08) 0)`,
                    }}
                  >
                    <div className="absolute inset-[10px] rounded-full bg-black/85" />
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                      <p className="text-[11px] uppercase tracking-[0.25em] text-zinc-400">MRI</p>
                      <p className={`text-5xl font-black ${mri.tone}`}>{stressResult.score.toFixed(0)}</p>
                      <p className="text-xs text-zinc-500">out of 100</p>
                    </div>
                  </div>
                  <p className={`mt-3 text-sm font-semibold ${mri.tone}`}>{mri.label}</p>
                </div>

                <div>
                  <p className="text-sm uppercase tracking-[0.2em] text-zinc-400">Secret Sauce Formula</p>
                  <p className="mt-1 text-sm text-zinc-300">
                    {stressResult.mri_formula || "MRI = 0.40 * Skill Match + 0.30 * Market Demand + 0.30 * Proof Density"}
                  </p>
                  <div className="mt-3 grid gap-3 text-sm md:grid-cols-3">
                    <div className="rounded-lg border border-white/10 bg-black/30 p-3">
                      <p className="text-xs uppercase tracking-wider text-zinc-500">Skill Match</p>
                      <p className="mt-1 text-lg font-semibold text-white">{stressResult.components.skill_overlap_score?.toFixed(1) ?? "0"}</p>
                    </div>
                    <div className="rounded-lg border border-white/10 bg-black/30 p-3">
                      <p className="text-xs uppercase tracking-wider text-zinc-500">Market Demand</p>
                      <p className="mt-1 text-lg font-semibold text-white">{stressResult.components.market_trend_score?.toFixed(1) ?? "0"}</p>
                    </div>
                    <div className="rounded-lg border border-white/10 bg-black/30 p-3">
                      <p className="text-xs uppercase tracking-wider text-zinc-500">Proof Density</p>
                      <p className="mt-1 text-lg font-semibold text-white">{stressResult.components.evidence_verification_score?.toFixed(1) ?? "0"}</p>
                    </div>
                  </div>
                  <div className="mt-3 grid gap-2 text-sm text-[color:var(--muted)] md:grid-cols-2">
                    <p>Trend: {trendLabel(stressResult.vacancy_trend_label)}</p>
                    <p>Job Stability (2027): {stressResult.job_stability_score_2027.toFixed(1)}</p>
                  </div>
                  <div className="mt-3 grid gap-3 text-sm md:grid-cols-2">
                    <div className="rounded-lg border border-white/10 bg-black/30 p-3">
                      <p className="text-xs uppercase tracking-wider text-zinc-500">Live Salary Benchmark</p>
                      <p className="mt-1 text-lg font-semibold text-white">
                        {typeof stressResult.salary_average === "number"
                          ? salaryFormatter.format(stressResult.salary_average)
                          : "Unavailable"}
                      </p>
                      <p className="text-xs text-[color:var(--muted)]">
                        {typeof stressResult.salary_percentile_local === "number"
                          ? `Local percentile: ${stressResult.salary_percentile_local.toFixed(1)}`
                          : "Percentile unavailable"}
                      </p>
                    </div>
                    <div className="rounded-lg border border-white/10 bg-black/30 p-3">
                      <p className="text-xs uppercase tracking-wider text-zinc-500">Skill Volatility Tracker</p>
                      <p className="mt-1 text-lg font-semibold text-white">
                        {((stressResult.vacancy_growth_percent ?? 0) >= 0 ? "+" : "") +
                          (stressResult.vacancy_growth_percent ?? 0).toFixed(1)}
                        % demand change
                      </p>
                      <p className="text-xs text-[color:var(--muted)]">
                        Volatility score: {(stressResult.market_volatility_score ?? 0).toFixed(1)} / 100
                      </p>
                    </div>
                  </div>
                </div>
              </div>
              <p className="mt-3 text-xs text-[color:var(--muted)]">
                Data freshness: {stressResult.data_freshness} | Providers: adzuna={stressResult.provider_status.adzuna},
                careeronestop={stressResult.provider_status.careeronestop}
              </p>
            </div>

            <div className="rounded-lg border border-[color:var(--border)] p-4">
              <p className="text-sm font-semibold text-white">Market Volatility Index (Live Adzuna)</p>
              <div className="mt-3 flex h-20 items-end gap-1">
                {stressResult.market_volatility_points.slice(-12).map((point, idx) => (
                  <div
                    key={`${point.x}-${idx}`}
                    className="w-3 rounded-t bg-[color:var(--accent-2)]/70"
                    style={{ height: `${Math.max(8, Math.min(88, (point.y / volatilityMax) * 88))}%` }}
                  />
                ))}
              </div>
              <label className="mt-4 block text-sm text-[color:var(--muted)]">
                2027 AI Automation Shift ({futureYear})
                <input className="mt-2 w-full" type="range" min={2026} max={2027} value={futureYear} onChange={(e) => setFutureYear(Number(e.target.value))} />
              </label>
              <p className="mt-2 text-sm text-[color:var(--muted)]">
                Projected MRI: <span className="font-semibold text-white">{projectedScore.toFixed(1)}</span>
                {futureYear === 2027 && (
                  <span className={`ml-3 font-semibold ${projectedDelta >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                    Delta {projectedDelta >= 0 ? "+" : ""}
                    {projectedDelta.toFixed(1)} | Risk {projectedRisk.toUpperCase()}
                  </span>
                )}
              </p>
              {futureYear === 2027 && simulation && (
                <div className="mt-2 grid gap-2 text-xs text-[color:var(--muted)] md:grid-cols-2">
                  <p>At risk skills: {simulation.at_risk_skills.join(", ") || "none detected"}</p>
                  <p>Growth skills: {simulation.growth_skills.join(", ") || "none detected"}</p>
                </div>
              )}
            </div>

            {Array.isArray(stressResult.top_hiring_companies) && stressResult.top_hiring_companies.length > 0 && (
              <div className="rounded-lg border border-[color:var(--border)] p-4">
                <p className="text-sm font-semibold text-white">Local Hero List (Top Hiring Companies)</p>
                <ul className="mt-2 grid gap-1 text-sm text-[color:var(--muted)]">
                  {stressResult.top_hiring_companies.slice(0, 5).map((company) => (
                    <li key={company.name}>
                      {company.name}: {company.open_roles} open roles in this search window
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {stressResult.citations && stressResult.citations.length > 0 && (
              <div className="rounded-lg border border-[color:var(--border)] p-4">
                <p className="text-sm font-semibold text-white">Confidence Citations</p>
                <ul className="mt-2 grid gap-2 text-sm text-[color:var(--muted)]">
                  {stressResult.citations.map((citation, idx) => (
                    <li key={`${citation.source}-${idx}`} className="rounded-md border border-white/10 bg-black/20 p-2">
                      <p className="font-medium text-white">{citation.source}</p>
                      <p className="text-xs">{citation.signal}: {String(citation.value)}</p>
                      {citation.note && <p className="text-xs">{citation.note}</p>}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="rounded-xl border border-[color:var(--border)] p-5">
        <h3 className="text-xl font-semibold">GitHub Proof Auditor</h3>
        <p className="mt-1 text-sm text-[color:var(--muted)]">
          Validation agent scans your public codebase and marks skills as Verified by Code.
        </p>
        <div className="mt-4 flex gap-3">
          <input
            className="w-full rounded-lg border border-[color:var(--border)] p-3"
            placeholder="https://github.com/owner or https://github.com/owner/repo"
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
          />
          <button className="cta" onClick={runRepoAudit} disabled={!isLoggedIn || repoLoading}>
            {repoLoading ? "Verifying..." : "Verify with GitHub"}
          </button>
        </div>
        {repoError && <p className="mt-3 text-sm text-[color:var(--accent-2)]">{repoError}</p>}
        {repoResult && (
          <div className="mt-4 grid gap-4 rounded-lg border border-[color:var(--border)] p-4">
            <p className="text-sm text-[color:var(--muted)]">
              Confidence: <span className="font-semibold text-white">{repoResult.repo_confidence.toFixed(1)}%</span>
            </p>
            <p className="text-sm text-[color:var(--muted)]">
              Verified by code: <span className="font-semibold text-white">{repoResult.match_count}</span> / {repoResult.required_skills_count}
            </p>
            <div className="h-2 w-full overflow-hidden rounded-full bg-black/40">
              <div
                className="h-full bg-emerald-400/80 transition-all"
                style={{
                  width: `${Math.max(
                    0,
                    Math.min(100, (repoResult.match_count / Math.max(repoResult.required_skills_count, 1)) * 100)
                  )}%`,
                }}
              />
            </div>
            <div>
              <p className="text-sm font-semibold text-white">Verified by code</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {repoResult.verified_by_repo_skills.length > 0 ? (
                  repoResult.verified_by_repo_skills.map((skill) => (
                    <span key={skill} className="rounded-full border border-green-500/50 bg-green-500/10 px-3 py-1 text-xs text-green-300">
                      Check: {skill}
                    </span>
                  ))
                ) : (
                  <span className="text-sm text-[color:var(--muted)]">No verified skills found.</span>
                )}
              </div>
            </div>
            <div>
              <p className="text-sm font-semibold text-white">Skill Gap Closing Targets</p>
              <ul className="mt-2 grid gap-1 text-sm text-[color:var(--muted)]">
                {repoResult.skills_required_but_missing.slice(0, 8).map((skill) => (
                  <li key={skill}>- {skill}</li>
                ))}
              </ul>
            </div>
            <p className="text-xs text-[color:var(--muted)]">
              Repos checked: {repoResult.repos_checked.join(", ") || "none"} | Languages detected: {repoResult.languages_detected.join(", ") || "none"}
            </p>
            <p className="text-xs text-[color:var(--muted)]">Files scanned: {repoResult.files_checked.join(", ") || "none"}</p>
          </div>
        )}
      </div>

      <div className="rounded-xl border border-[color:var(--border)] p-5">
        <h3 className="text-xl font-semibold">90-Day Agentic Mission Dashboard</h3>
        <p className="mt-1 text-sm text-[color:var(--muted)]">
          Not generic advice. A schedule tied to your missing skills, local market demand, and available hours.
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <button className="cta" onClick={() => runOrchestrator(false)} disabled={!isLoggedIn || orchestratorLoading}>
            {orchestratorLoading ? "Building mission..." : "Generate 90-Day Mission"}
          </button>
          <button className="cta cta-secondary" onClick={() => runOrchestrator(true)} disabled={!isLoggedIn || pivotLoading}>
            {pivotLoading ? "Pivoting..." : "Market Pivot"}
          </button>
          <button className="cta cta-secondary" onClick={exportMissionPlan} disabled={!orchestratorResult}>
            Export 90-Day Mission
          </button>
        </div>
        {orchestratorError && <p className="mt-3 text-sm text-[color:var(--accent-2)]">{orchestratorError}</p>}
        {pivotError && <p className="mt-2 text-sm text-[color:var(--accent-2)]">{pivotError}</p>}
        {orchestratorResult && (
          <div className="mt-4 grid gap-4">
            <div className="rounded-lg border border-[color:var(--border)] p-4">
              <p className="text-sm font-semibold text-white">Market Alert</p>
              <p className="mt-2 text-sm text-[color:var(--muted)]">{orchestratorResult.market_alert}</p>
              {orchestratorResult.pivot_reason && (
                <p className="mt-2 text-xs text-[color:var(--muted)]">
                  {orchestratorResult.pivot_reason}
                  {orchestratorResult.pivot_target_role ? ` | Focus role: ${orchestratorResult.pivot_target_role}` : ""}
                </p>
              )}
            </div>
            <div className="rounded-lg border border-[color:var(--border)] p-4">
              <p className="text-sm font-semibold text-white">Interactive Mission Kanban</p>
              <p className="mt-1 text-xs text-[color:var(--muted)]">
                Agentic execution board tied to market audit output. Progress: {kanbanDoneCount}/{kanbanTasks.length || 0} ({kanbanProgressPct}%)
              </p>
              <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-black/40">
                <div className="h-full bg-emerald-400/80 transition-all" style={{ width: `${kanbanProgressPct}%` }} />
              </div>
              <div className="mt-3 grid gap-3 md:grid-cols-3">
                {[
                  { lane: "backlog" as const, title: "Backlog" },
                  { lane: "in_progress" as const, title: "In Progress" },
                  { lane: "done" as const, title: "Done" },
                ].map((column) => (
                  <div key={column.lane} className="rounded-lg border border-white/10 bg-black/20 p-3">
                    <p className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                      {column.title} ({kanbanTasks.filter((task) => task.lane === column.lane).length})
                    </p>
                    <div className="mt-2 grid gap-2">
                      {kanbanTasks
                        .filter((task) => task.lane === column.lane)
                        .map((task) => (
                          <div key={task.id} className="rounded-md border border-white/10 bg-black/40 p-2">
                            <p className="text-xs text-[color:var(--muted)]">{task.phase}</p>
                            <p className="text-sm text-white">{task.label}</p>
                            <div className="mt-2 flex flex-wrap gap-2">
                              {task.lane !== "backlog" && (
                                <button className="cta cta-secondary" onClick={() => moveKanbanTask(task.id, "backlog")}>
                                  Backlog
                                </button>
                              )}
                              {task.lane !== "in_progress" && (
                                <button className="cta cta-secondary" onClick={() => moveKanbanTask(task.id, "in_progress")}>
                                  Start
                                </button>
                              )}
                              {task.lane !== "done" && (
                                <button className="cta cta-secondary" onClick={() => moveKanbanTask(task.id, "done")}>
                                  Done
                                </button>
                              )}
                            </div>
                          </div>
                        ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-lg border border-[color:var(--border)] p-3">
                <p className="font-semibold text-white">Day 0-30</p>
                <ul className="mt-2 grid gap-1 text-sm text-[color:var(--muted)]">
                  {day0.map((item) => (
                    <li key={item}>- {item}</li>
                  ))}
                </ul>
              </div>
              <div className="rounded-lg border border-[color:var(--border)] p-3">
                <p className="font-semibold text-white">Day 31-60</p>
                <ul className="mt-2 grid gap-1 text-sm text-[color:var(--muted)]">
                  {day31.map((item) => (
                    <li key={item}>- {item}</li>
                  ))}
                </ul>
              </div>
              <div className="rounded-lg border border-[color:var(--border)] p-3">
                <p className="font-semibold text-white">Day 61-90</p>
                <ul className="mt-2 grid gap-1 text-sm text-[color:var(--muted)]">
                  {day61.map((item) => (
                    <li key={item}>- {item}</li>
                  ))}
                </ul>
              </div>
            </div>
            <div className="rounded-lg border border-[color:var(--border)] p-4">
              <p className="text-sm font-semibold text-white">Weekly checkboxes</p>
              <p className="mt-1 text-xs text-[color:var(--muted)]">
                Progress: {weeklyCompleted}/{weekly.length || 0} completed ({weeklyProgressPct}%)
              </p>
              <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-black/40">
                <div className="h-full bg-[color:var(--accent-2)]/80 transition-all" style={{ width: `${weeklyProgressPct}%` }} />
              </div>
              <div className="mt-2 grid gap-2">
                {weekly.map((item) => (
                  <label key={item} className="flex items-start gap-2 text-sm text-[color:var(--muted)]">
                    <input
                      type="checkbox"
                      className="mt-0.5"
                      checked={Boolean(weeklyChecks[item])}
                      onChange={() =>
                        setWeeklyChecks((prev) => ({
                          ...prev,
                          [item]: !prev[item],
                        }))
                      }
                    />
                    <span>{item}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="rounded-xl border border-[color:var(--border)] bg-black/30 p-4 text-sm text-[color:var(--muted)]">
        <p className="font-semibold text-white">Tip of the Day</p>
        <p className="mt-1">{strategicTip}</p>
      </div>
    </section>
  );
}
