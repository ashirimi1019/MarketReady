"use client";

import { useEffect, useMemo, useState } from "react";
import { apiGet } from "@/lib/api";
import { useSession } from "@/lib/session";

type Milestone = {
  milestone_id: string;
  title: string;
  description?: string | null;
  semester_index: number;
};

function toYearTitle(title: string): string {
  return title.replace(/semester\s+(\d+)/i, "Year $1");
}

export default function StudentTimelinePage() {
  const { username, isLoggedIn } = useSession();
  const [milestones, setMilestones] = useState<Milestone[]>([]);

  const headers = useMemo(() => ({ "X-User-Id": username }), [username]);

  useEffect(() => {
    if (!isLoggedIn) return;
    apiGet<Milestone[]>("/user/timeline", headers)
      .then(setMilestones)
      .catch(() => setMilestones([]));
  }, [headers, isLoggedIn]);

  return (
    <section className="panel">
      <h2 className="text-2xl font-semibold">Timeline</h2>
      <p className="mt-2 text-[color:var(--muted)]">
        Milestones align with year-by-year pacing and pathway proofs.
      </p>
      {!isLoggedIn && (
        <p className="mt-4 text-sm text-[color:var(--accent-2)]">
          Please log in to view your timeline.
        </p>
      )}
      <div className="mt-6 grid gap-4">
        {milestones.map((item) => (
          <div
            key={item.title}
            className="flex items-center justify-between rounded-xl border border-[color:var(--border)] p-4"
          >
            <div>
              <p className="font-medium">{toYearTitle(item.title)}</p>
              <p className="text-sm text-[color:var(--muted)]">
                {item.description ?? "No description."}
              </p>
            </div>
            <span className="text-xs text-[color:var(--muted)]">
              Year {item.semester_index}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
