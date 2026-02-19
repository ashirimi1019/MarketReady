"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet, apiSend } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { AiInterviewSession } from "@/types/api";

type DraftAnswer = {
  answer_text: string;
  video_url: string;
};

export default function StudentInterviewPage() {
  const { username, isLoggedIn } = useSession();
  const headers = useMemo(() => ({ "X-User-Id": username }), [username]);

  const [targetRole, setTargetRole] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [questionCount, setQuestionCount] = useState(5);
  const [sessions, setSessions] = useState<AiInterviewSession[]>([]);
  const [activeSession, setActiveSession] = useState<AiInterviewSession | null>(null);
  const [drafts, setDrafts] = useState<Record<string, DraftAnswer>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const loadSessions = useCallback(() => {
    if (!isLoggedIn) return;
    apiGet<AiInterviewSession[]>("/user/ai/interview/sessions", headers)
      .then(setSessions)
      .catch(() => setSessions([]));
  }, [headers, isLoggedIn]);

  const loadSessionDetail = useCallback(
    async (sessionId: string) => {
      if (!isLoggedIn) return;
      try {
        const data = await apiGet<AiInterviewSession>(
          `/user/ai/interview/sessions/${sessionId}`,
          headers
        );
        setActiveSession(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not load interview session.");
      }
    },
    [headers, isLoggedIn]
  );

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const createSession = async () => {
    if (!isLoggedIn) {
      setError("Please log in to start interview practice.");
      return;
    }
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const session = await apiSend<AiInterviewSession>("/user/ai/interview/sessions", {
        method: "POST",
        headers: {
          ...headers,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          target_role: targetRole.trim() || null,
          job_description: jobDescription.trim() || null,
          question_count: questionCount,
        }),
      });
      setActiveSession(session);
      setMessage("Interview session generated.");
      loadSessions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create interview session.");
    } finally {
      setLoading(false);
    }
  };

  const submitAnswer = async (questionId: string) => {
    if (!isLoggedIn || !activeSession) return;
    const draft = drafts[questionId] ?? { answer_text: "", video_url: "" };
    setError(null);
    setMessage(null);
    try {
      await apiSend(
        `/user/ai/interview/sessions/${activeSession.id}/responses`,
        {
          method: "POST",
          headers: {
            ...headers,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            question_id: questionId,
            answer_text: draft.answer_text.trim() || null,
            video_url: draft.video_url.trim() || null,
          }),
        }
      );
      setMessage("Response scored.");
      await loadSessionDetail(activeSession.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not score response.");
    }
  };

  const getResponse = (questionId: string) =>
    activeSession?.responses.find((row) => row.question_id === questionId);

  return (
    <section className="panel">
      <h2 className="text-3xl font-semibold">AI Interview Simulator · Powered by OpenAI</h2>
      <p className="mt-2 text-[color:var(--muted)]">
        Practice interview questions generated from your proof-backed milestones.
      </p>
      {!isLoggedIn && (
        <p className="mt-4 text-sm text-[color:var(--accent-2)]">
          Please log in to run interview simulations.
        </p>
      )}
      {error && <p className="mt-4 text-sm text-[color:var(--accent-2)]">{error}</p>}
      {message && <p className="mt-4 text-sm text-[color:var(--muted)]">{message}</p>}

      <div className="mt-6 grid gap-3 md:grid-cols-2">
        <label className="text-sm text-[color:var(--muted)]" htmlFor="interview-role">
          Target role (optional)
          <input
            id="interview-role"
            className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
            value={targetRole}
            onChange={(event) => setTargetRole(event.target.value)}
            placeholder="e.g., Full-Stack Engineer Intern"
          />
        </label>
        <label className="text-sm text-[color:var(--muted)]" htmlFor="interview-count">
          Number of questions
          <input
            id="interview-count"
            type="number"
            min={3}
            max={10}
            className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
            value={questionCount}
            onChange={(event) => setQuestionCount(Number(event.target.value) || 5)}
          />
        </label>
      </div>
      <label className="mt-3 block text-sm text-[color:var(--muted)]" htmlFor="interview-jobdesc">
        Job description (optional)
        <textarea
          id="interview-jobdesc"
          className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
          rows={4}
          value={jobDescription}
          onChange={(event) => setJobDescription(event.target.value)}
          placeholder="Paste role requirements for more targeted questions."
        />
      </label>
      <div className="mt-4 flex flex-wrap gap-3">
        <button className="cta" onClick={createSession} disabled={!isLoggedIn || loading}>
          {loading ? "Generating..." : "Start Interview"}
        </button>
        <button className="cta cta-secondary" onClick={loadSessions} disabled={!isLoggedIn}>
          Refresh Sessions
        </button>
      </div>

      {sessions.length > 0 && (
        <div className="mt-8">
          <h3 className="text-xl font-semibold">Recent Sessions</h3>
          <div className="mt-3 grid gap-3">
            {sessions.map((session) => (
              <div
                key={session.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[color:var(--border)] p-4"
              >
                <div>
                  <p className="font-medium">
                    {session.target_role || "General Interview"} ({session.question_count} questions)
                  </p>
                  <p className="text-sm text-[color:var(--muted)]">
                    {session.status} · {new Date(session.created_at).toLocaleString()}
                  </p>
                </div>
                <button
                  className="cta cta-secondary"
                  onClick={() => loadSessionDetail(session.id)}
                >
                  Open
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeSession && (
        <div className="mt-8">
          <h3 className="text-xl font-semibold">Active Session</h3>
          <p className="mt-2 text-sm text-[color:var(--muted)]">
            {activeSession.summary || "Answer each question. OpenAI will score and coach you."}
          </p>
          <div className="mt-4 grid gap-4">
            {activeSession.questions.map((question) => {
              const response = getResponse(question.id);
              const draft = drafts[question.id] ?? { answer_text: "", video_url: "" };
              return (
                <div
                  key={question.id}
                  className="rounded-xl border border-[color:var(--border)] p-4"
                >
                  <p className="text-sm text-[color:var(--muted)]">
                    Q{question.order_index} · {question.difficulty || "intermediate"}
                  </p>
                  <p className="mt-1 font-medium">{question.prompt}</p>
                  {(question.focus_title || question.focus_milestone_title) && (
                    <p className="mt-1 text-sm text-[color:var(--muted)]">
                      Focus: {question.focus_title || question.focus_milestone_title}
                    </p>
                  )}

                  <label
                    className="mt-3 block text-sm text-[color:var(--muted)]"
                    htmlFor={`answer-${question.id}`}
                  >
                    Answer transcript
                    <textarea
                      id={`answer-${question.id}`}
                      className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
                      rows={4}
                      value={draft.answer_text}
                      onChange={(event) =>
                        setDrafts((prev) => ({
                          ...prev,
                          [question.id]: {
                            ...draft,
                            answer_text: event.target.value,
                          },
                        }))
                      }
                    />
                  </label>
                  <label
                    className="mt-3 block text-sm text-[color:var(--muted)]"
                    htmlFor={`video-${question.id}`}
                  >
                    Video URL (optional)
                    <input
                      id={`video-${question.id}`}
                      className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
                      value={draft.video_url}
                      onChange={(event) =>
                        setDrafts((prev) => ({
                          ...prev,
                          [question.id]: {
                            ...draft,
                            video_url: event.target.value,
                          },
                        }))
                      }
                      placeholder="https://..."
                    />
                  </label>
                  <div className="mt-3">
                    <button
                      className="cta cta-secondary"
                      onClick={() => submitAnswer(question.id)}
                      disabled={!isLoggedIn}
                    >
                      Score Answer
                    </button>
                  </div>

                  {response && (
                    <div className="mt-4 rounded-lg border border-[color:var(--border)] p-3">
                      <p className="text-sm text-[color:var(--muted)]">
                        OpenAI score: {response.ai_score?.toFixed(1) ?? "--"} / 100
                        {response.confidence !== null && response.confidence !== undefined
                          ? ` · confidence ${(response.confidence * 100).toFixed(0)}%`
                          : ""}
                      </p>
                      <p className="mt-2 text-sm text-[color:var(--muted)]">
                        {response.ai_feedback || "No feedback yet."}
                      </p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}
