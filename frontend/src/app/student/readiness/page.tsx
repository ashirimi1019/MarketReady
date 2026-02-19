"use client";

import { useEffect, useMemo, useState } from "react";
import { apiGet, apiSend } from "@/lib/api";
import { useSession } from "@/lib/session";

type Readiness = {
  score: number;
  band: string;
  capped: boolean;
  cap_reason?: string | null;
  next_actions: string[];
  top_gaps: string[];
};

type ChecklistItem = {
  id: string;
  title: string;
};

type AiGuide = {
  decision?: string | null;
  recommendations?: string[];
  priority_focus_areas?: string[];
  weekly_plan?: string[];
  uncertainty?: string | null;
};

export default function StudentReadinessPage() {
  const { username, isLoggedIn } = useSession();
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [itemMap, setItemMap] = useState<Record<string, string>>({});
  const [guide, setGuide] = useState<AiGuide | null>(null);
  const [guideLoading, setGuideLoading] = useState(false);
  const [guideError, setGuideError] = useState<string | null>(null);

  const headers = useMemo(() => ({ "X-User-Id": username }), [username]);

  useEffect(() => {
    if (!isLoggedIn) return;
    apiGet<Readiness>("/user/readiness", headers)
      .then(setReadiness)
      .catch(() => setReadiness(null));
  }, [headers, isLoggedIn]);

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
  }, [isLoggedIn]);

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
        <h3 className="text-2xl font-semibold">AI Guide Summary</h3>
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
