"use client";

import { useEffect, useMemo, useState } from "react";
import { apiGet, apiSend } from "@/lib/api";
import { useSession } from "@/lib/session";
import type {
  Readiness,
  ChecklistItem,
  AiGuide,
  ReadinessRank,
  WeeklyMilestoneStreak,
} from "@/types/api";

export default function StudentReadinessPage() {
  const { username, isLoggedIn } = useSession();
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [itemMap, setItemMap] = useState<Record<string, string>>({});
  const [guide, setGuide] = useState<AiGuide | null>(null);
  const [guideLoading, setGuideLoading] = useState(false);
  const [guideError, setGuideError] = useState<string | null>(null);
  const [rank, setRank] = useState<ReadinessRank | null>(null);
  const [streak, setStreak] = useState<WeeklyMilestoneStreak | null>(null);
  const [shareStatus, setShareStatus] = useState<string | null>(null);

  const headers = useMemo(() => ({ "X-User-Id": username }), [username]);

  useEffect(() => {
    if (!isLoggedIn) return;
    apiGet<Readiness>("/user/readiness", headers)
      .then(setReadiness)
      .catch(() => setReadiness(null));
  }, [headers, isLoggedIn]);

  useEffect(() => {
    if (!isLoggedIn) return;
    apiGet<ReadinessRank>("/user/readiness/rank", headers)
      .then(setRank)
      .catch(() => setRank(null));
  }, [headers, isLoggedIn]);

  useEffect(() => {
    if (!isLoggedIn) return;
    apiGet<WeeklyMilestoneStreak>("/user/streak", headers)
      .then(setStreak)
      .catch(() => setStreak(null));
  }, [headers, isLoggedIn]);

  const generateGuide = async () => {
    if (!isLoggedIn) {
      setGuideError("Please log in to generate OpenAI guidance.");
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
      setGuideError(err instanceof Error ? err.message : "OpenAI guide unavailable.");
    } finally {
      setGuideLoading(false);
    }
  };

  useEffect(() => {
    if (!isLoggedIn) return;
    apiGet<ChecklistItem[]>("/user/checklist", headers)
      .then((items) => {
        const map: Record<string, string> = {};
        items.forEach((item) => {
          map[item.title] = item.id;
        });
        setItemMap(map);
      })
      .catch(() => setItemMap({}));
  }, [headers, isLoggedIn]);

  useEffect(() => {
    if (isLoggedIn) return;
    setGuide(null);
    setGuideError(null);
    setGuideLoading(false);
    setRank(null);
    setStreak(null);
    setShareStatus(null);
  }, [isLoggedIn]);

  const copyShareText = async () => {
    if (!rank) return;
    setShareStatus(null);
    try {
      await navigator.clipboard.writeText(rank.linkedin_share_text);
      setShareStatus("Share text copied.");
    } catch {
      setShareStatus("Could not copy share text.");
    }
  };

  return (
    <section className="panel">
      <h2 className="text-3xl font-semibold">Readiness Score</h2>
      <p className="mt-2 text-[color:var(--muted)]">
        Scores are out of 100 and capped if critical proof is missing.
      </p>
      {!isLoggedIn && (
        <p className="mt-4 text-sm text-[color:var(--accent-2)]">
          Please log in to view your readiness score.
        </p>
      )}
      <div className="mt-8 grid gap-5 md:grid-cols-3">
        <div className="rounded-2xl border border-[color:var(--border)] p-6">
          <p className="text-base text-[color:var(--muted)]">Score</p>
          <p className="mt-2 text-4xl font-semibold">
            {readiness ? readiness.score.toFixed(0) : "--"}
          </p>
        </div>
        <div className="rounded-2xl border border-[color:var(--border)] p-6">
          <p className="text-base text-[color:var(--muted)]">Band</p>
          <p className="mt-2 text-2xl font-semibold">
            {readiness?.band ?? "--"}
          </p>
        </div>
        <div className="rounded-2xl border border-[color:var(--border)] p-6">
          <p className="text-base text-[color:var(--muted)]">Cap Reason</p>
          <p className="mt-2 text-base">
            {readiness?.cap_reason ?? "None"}
          </p>
        </div>
      </div>
      <div className="mt-5 grid gap-5 md:grid-cols-3">
        <div className="rounded-2xl border border-[color:var(--border)] p-6">
          <p className="text-base text-[color:var(--muted)]">Percentile</p>
          <p className="mt-2 text-3xl font-semibold">
            {rank ? `${rank.percentile.toFixed(1)}%` : "--"}
          </p>
        </div>
        <div className="rounded-2xl border border-[color:var(--border)] p-6">
          <p className="text-base text-[color:var(--muted)]">Global Rank</p>
          <p className="mt-2 text-3xl font-semibold">
            {rank ? `#${rank.rank}` : "--"}
          </p>
          <p className="mt-1 text-sm text-[color:var(--muted)]">
            {rank ? `of ${rank.total_students} students` : ""}
          </p>
        </div>
        <div className="rounded-2xl border border-[color:var(--border)] p-6">
          <p className="text-base text-[color:var(--muted)]">Milestone Streak</p>
          <p className="mt-2 text-3xl font-semibold">
            {streak ? `${streak.current_streak_weeks}w` : "--"}
          </p>
          <p className="mt-1 text-sm text-[color:var(--muted)]">
            longest {streak?.longest_streak_weeks ?? 0}w
          </p>
        </div>
      </div>
      <div className="mt-5 rounded-xl border border-[color:var(--border)] p-4">
        <h3 className="text-lg font-semibold">Share On LinkedIn</h3>
        <p className="mt-2 text-sm text-[color:var(--muted)]">
          Share your readiness percentile like a career credit score.
        </p>
        <div className="mt-3 flex flex-wrap gap-3">
          <button className="cta cta-secondary" onClick={copyShareText} disabled={!rank}>
            Copy Share Text
          </button>
          {rank && (
            <a
              className="cta cta-secondary"
              href={rank.linkedin_share_url}
              target="_blank"
              rel="noreferrer"
            >
              Open LinkedIn Share
            </a>
          )}
        </div>
        {rank && (
          <p className="mt-3 text-sm text-[color:var(--muted)]">
            {rank.linkedin_share_text}
          </p>
        )}
        {shareStatus && (
          <p className="mt-2 text-sm text-[color:var(--muted)]">{shareStatus}</p>
        )}
      </div>
      <div className="mt-8">
        <h3 className="text-2xl font-semibold">Next Actions</h3>
        <ul className="mt-4 grid gap-3 text-base text-[color:var(--muted)]">
          {readiness?.next_actions?.length ? (
            readiness.next_actions.map((action) => (
              <li key={action}>{action}</li>
            ))
          ) : (
            <li>No actions available.</li>
          )}
        </ul>
      </div>
      <div className="mt-8">
        <h3 className="text-2xl font-semibold">Top Gaps</h3>
        <ul className="mt-4 grid gap-3 text-base text-[color:var(--muted)]">
          {readiness?.top_gaps?.length ? (
            readiness.top_gaps.map((gap) => {
              const itemId = itemMap[gap];
              return (
                <li key={gap}>
                  {itemId ? (
                    <a
                      className="text-[color:var(--accent-2)] underline"
                      href={`/student/checklist?item=${itemId}`}
                    >
                      {gap}
                    </a>
                  ) : (
                    gap
                  )}
                </li>
              );
            })
          ) : (
            <li>No gaps identified.</li>
          )}
        </ul>
      </div>
      <div className="mt-8">
        <h3 className="text-2xl font-semibold">AI Guide Summary · Powered by OpenAI</h3>
        <p className="mt-2 text-[color:var(--muted)]">
          Decision + recommendations grounded in your profile and checklist.
        </p>
        <div className="mt-4">
          <button className="cta" onClick={generateGuide} disabled={!isLoggedIn || guideLoading}>
            {guideLoading ? "Generating guidance..." : "Generate Guidance"}
          </button>
        </div>
        {!guide && !guideLoading && !guideError && isLoggedIn && (
          <p className="mt-3 text-sm text-[color:var(--muted)]">
            Guidance is generated only after you click the button.
          </p>
        )}
        {guideLoading && (
          <p className="mt-3 text-sm text-[color:var(--muted)]">
            Generating guidance...
          </p>
        )}
        {guideError && (
          <p className="mt-3 text-sm text-[color:var(--accent-2)]">{guideError}</p>
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
            <div className="rounded-xl border border-[color:var(--border)] p-4">
              <p className="text-sm text-[color:var(--muted)]">Priority Focus</p>
              <ul className="mt-2 grid gap-2 text-[color:var(--muted)]">
                {guide.priority_focus_areas?.length ? (
                  guide.priority_focus_areas.map((item) => <li key={item}>{item}</li>)
                ) : (
                  <li>No focus priorities yet.</li>
                )}
              </ul>
            </div>
            <div className="rounded-xl border border-[color:var(--border)] p-4 md:col-span-2">
              <p className="text-sm text-[color:var(--muted)]">Weekly Plan</p>
              <ul className="mt-2 grid gap-2 text-[color:var(--muted)]">
                {guide.weekly_plan?.length ? (
                  guide.weekly_plan.map((item) => <li key={item}>{item}</li>)
                ) : (
                  <li>No weekly plan generated yet.</li>
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
      </div>
    </section>
  );
}
