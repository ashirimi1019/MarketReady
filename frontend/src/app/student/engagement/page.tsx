"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet, apiSend } from "@/lib/api";
import { useSession } from "@/lib/session";

type Goal = {
  id: string;
  title: string;
  description?: string | null;
  status: string;
  target_date?: string | null;
  last_check_in_at?: string | null;
  streak_days: number;
};

type Notification = {
  id: string;
  kind: string;
  message: string;
  is_read: boolean;
  created_at: string;
};

type EngagementSummary = {
  goals_total: number;
  goals_completed: number;
  active_streak_days: number;
  unread_notifications: number;
  next_deadlines: string[];
};

type WeeklyMilestoneStreak = {
  current_streak_weeks: number;
  longest_streak_weeks: number;
  total_active_weeks: number;
  active_this_week: boolean;
  rewards: string[];
  next_reward_at_weeks?: number | null;
  recent_weeks: { week_label: string; has_activity: boolean }[];
};

export default function StudentEngagementPage() {
  const { username, isLoggedIn } = useSession();
  const headers = useMemo(() => ({ "X-User-Id": username }), [username]);

  const [goals, setGoals] = useState<Goal[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [summary, setSummary] = useState<EngagementSummary | null>(null);
  const [weeklyStreak, setWeeklyStreak] = useState<WeeklyMilestoneStreak | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [targetDate, setTargetDate] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  const loadAll = useCallback(() => {
    if (!isLoggedIn) return;
    apiGet<Goal[]>("/user/goals", headers).then(setGoals).catch(() => setGoals([]));
    apiGet<Notification[]>("/user/notifications", headers)
      .then(setNotifications)
      .catch(() => setNotifications([]));
    apiGet<EngagementSummary>("/user/engagement/summary", headers)
      .then(setSummary)
      .catch(() => setSummary(null));
    apiGet<WeeklyMilestoneStreak>("/user/streak", headers)
      .then(setWeeklyStreak)
      .catch(() => setWeeklyStreak(null));
  }, [headers, isLoggedIn]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const addGoal = async () => {
    if (!title.trim()) {
      setMessage("Goal title is required.");
      return;
    }
    try {
      await apiSend("/user/goals", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          description: description || null,
          target_date: targetDate ? new Date(targetDate).toISOString() : null,
        }),
      });
      setTitle("");
      setDescription("");
      setTargetDate("");
      setMessage("Goal added.");
      loadAll();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Could not add goal.");
    }
  };

  const checkInGoal = async (goalId: string) => {
    try {
      await apiSend(`/user/goals/${goalId}/check-in`, {
        method: "POST",
        headers,
      });
      loadAll();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Check-in failed.");
    }
  };

  const completeGoal = async (goalId: string) => {
    try {
      await apiSend(`/user/goals/${goalId}`, {
        method: "PUT",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ status: "completed" }),
      });
      loadAll();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Update failed.");
    }
  };

  const generateReminders = async () => {
    try {
      await apiSend<Notification[]>("/user/notifications/generate", {
        method: "POST",
        headers,
      });
      loadAll();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Reminder generation failed.");
    }
  };

  const markRead = async (id: string) => {
    try {
      await apiSend(`/user/notifications/${id}/read`, {
        method: "POST",
        headers,
      });
      loadAll();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Could not mark notification.");
    }
  };

  return (
    <section className="panel">
      <h2 className="text-3xl font-semibold">Goals & Engagement</h2>
      <p className="mt-2 text-[color:var(--muted)]">
        Track weekly goals, streaks, and reminders.
      </p>
      {!isLoggedIn && (
        <p className="mt-4 text-sm text-[color:var(--accent-2)]">
          Please log in to use engagement features.
        </p>
      )}
      {message && <p className="mt-3 text-sm text-[color:var(--muted)]">{message}</p>}

      <div className="mt-6 grid gap-4 md:grid-cols-4">
        <div className="rounded-xl border border-[color:var(--border)] p-4">
          <p className="text-sm text-[color:var(--muted)]">Goals</p>
          <p className="text-2xl font-semibold">{summary?.goals_total ?? 0}</p>
        </div>
        <div className="rounded-xl border border-[color:var(--border)] p-4">
          <p className="text-sm text-[color:var(--muted)]">Completed</p>
          <p className="text-2xl font-semibold">{summary?.goals_completed ?? 0}</p>
        </div>
        <div className="rounded-xl border border-[color:var(--border)] p-4">
          <p className="text-sm text-[color:var(--muted)]">Best Streak</p>
          <p className="text-2xl font-semibold">{summary?.active_streak_days ?? 0}d</p>
        </div>
        <div className="rounded-xl border border-[color:var(--border)] p-4">
          <p className="text-sm text-[color:var(--muted)]">Unread Alerts</p>
          <p className="text-2xl font-semibold">{summary?.unread_notifications ?? 0}</p>
        </div>
      </div>
      <div className="mt-4 rounded-xl border border-[color:var(--border)] p-4">
        <p className="text-sm text-[color:var(--muted)]">Milestone Streak (weekly)</p>
        <p className="mt-1 text-xl font-semibold">
          {weeklyStreak?.current_streak_weeks ?? 0} week(s)
        </p>
        <p className="mt-1 text-sm text-[color:var(--muted)]">
          Longest: {weeklyStreak?.longest_streak_weeks ?? 0} week(s) · Active weeks:{" "}
          {weeklyStreak?.total_active_weeks ?? 0}
        </p>
        {weeklyStreak?.rewards?.length ? (
          <p className="mt-1 text-sm text-[color:var(--muted)]">
            Rewards: {weeklyStreak.rewards.join(", ")}
          </p>
        ) : (
          <p className="mt-1 text-sm text-[color:var(--muted)]">
            Next reward at {weeklyStreak?.next_reward_at_weeks ?? 2} weeks.
          </p>
        )}
        {weeklyStreak?.recent_weeks?.length ? (
          <div className="mt-3 flex flex-wrap gap-2 text-xs">
            {weeklyStreak.recent_weeks.map((week) => (
              <span
                key={week.week_label}
                className={`rounded-full border px-3 py-1 ${
                  week.has_activity
                    ? "border-[color:var(--accent-2)] text-[color:var(--accent-2)]"
                    : "border-[color:var(--border)] text-[color:var(--muted)]"
                }`}
              >
                {week.week_label}
              </span>
            ))}
          </div>
        ) : null}
      </div>

      <div className="divider" />

      <h3 className="text-xl font-semibold">Create Goal</h3>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <label
          htmlFor="engagement-goal-title"
          className="text-sm text-[color:var(--muted)]"
        >
          Goal title
          <input
            id="engagement-goal-title"
            className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
            placeholder="Goal title"
            value={title}
            title="Goal title"
            aria-label="Goal title"
            onChange={(event) => setTitle(event.target.value)}
          />
        </label>
        <label
          htmlFor="engagement-goal-description"
          className="text-sm text-[color:var(--muted)]"
        >
          Description
          <input
            id="engagement-goal-description"
            className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
            placeholder="Description"
            value={description}
            title="Goal description"
            aria-label="Goal description"
            onChange={(event) => setDescription(event.target.value)}
          />
        </label>
        <label
          htmlFor="engagement-goal-target-date"
          className="text-sm text-[color:var(--muted)]"
        >
          Target date
          <input
            id="engagement-goal-target-date"
            type="date"
            className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
            value={targetDate}
            title="Target date"
            aria-label="Target date"
            onChange={(event) => setTargetDate(event.target.value)}
          />
        </label>
      </div>
      <div className="mt-3 flex flex-wrap gap-3">
        <button className="cta" onClick={addGoal}>
          Add Goal
        </button>
        <button className="cta cta-secondary" onClick={generateReminders}>
          Generate Reminders
        </button>
      </div>

      <div className="divider" />

      <h3 className="text-xl font-semibold">Goal List</h3>
      <div className="mt-4 grid gap-3">
        {goals.length === 0 && (
          <p className="text-sm text-[color:var(--muted)]">No goals yet.</p>
        )}
        {goals.map((goal) => (
          <div key={goal.id} className="rounded-xl border border-[color:var(--border)] p-4">
            <p className="font-medium">{goal.title}</p>
            <p className="text-sm text-[color:var(--muted)]">
              {goal.description || "No description"} | Status: {goal.status} | Streak:{" "}
              {goal.streak_days}d
            </p>
            {goal.target_date && (
              <p className="text-xs text-[color:var(--muted)]">
                Target: {new Date(goal.target_date).toLocaleDateString()}
              </p>
            )}
            <div className="mt-2 flex flex-wrap gap-2">
              <button className="cta cta-secondary" onClick={() => checkInGoal(goal.id)}>
                Check-in
              </button>
              {goal.status !== "completed" && (
                <button className="cta cta-secondary" onClick={() => completeGoal(goal.id)}>
                  Mark Completed
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="divider" />

      <h3 className="text-xl font-semibold">Notifications</h3>
      <div className="mt-4 grid gap-3">
        {notifications.length === 0 && (
          <p className="text-sm text-[color:var(--muted)]">No notifications yet.</p>
        )}
        {notifications.map((note) => (
          <div key={note.id} className="rounded-xl border border-[color:var(--border)] p-4">
            <p className="font-medium">{note.kind}</p>
            <p className="text-sm text-[color:var(--muted)]">{note.message}</p>
            <p className="text-xs text-[color:var(--muted)]">
              {new Date(note.created_at).toLocaleString()}
            </p>
            {!note.is_read && (
              <button className="cta cta-secondary mt-2" onClick={() => markRead(note.id)}>
                Mark Read
              </button>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
