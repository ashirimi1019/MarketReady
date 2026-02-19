"use client";

import { useEffect, useMemo, useState } from "react";
import { apiGet, apiSend } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { ChecklistItem, AiGuide } from "@/types/api";

export default function StudentAiGuidePage() {
  const { username, isLoggedIn } = useSession();
  const headers = useMemo(() => ({ "X-User-Id": username }), [username]);
  const [question, setQuestion] = useState("");
  const [guide, setGuide] = useState<AiGuide | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [needsOnboarding, setNeedsOnboarding] = useState(false);
  const [checklistMap, setChecklistMap] = useState<Record<string, ChecklistItem>>(
    {}
  );
  const [feedbackComment, setFeedbackComment] = useState("");
  const [feedbackStatus, setFeedbackStatus] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoggedIn) return;
    apiGet<ChecklistItem[]>("/user/checklist", headers)
      .then((items) => {
        const map: Record<string, ChecklistItem> = {};
        items.forEach((item) => {
          map[item.id] = item;
        });
        setChecklistMap(map);
      })
      .catch(() => setChecklistMap({}));
  }, [headers, isLoggedIn]);

  const loadGuide = async (prompt?: string) => {
    if (!isLoggedIn) {
      setError("Please log in to use the OpenAI guide.");
      return;
    }
    setLoading(true);
    setError(null);
    setNeedsOnboarding(false);
    try {
      const data = await apiSend<AiGuide>("/user/ai/guide", {
        method: "POST",
        headers: {
          ...headers,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ question: prompt?.trim() || null }),
      });
      setGuide(data);
    } catch (err) {
      const raw = err instanceof Error ? err.message : "Failed to load OpenAI guidance.";
      if (raw.includes("No pathway selection found")) {
        setNeedsOnboarding(true);
        setError(
          "Complete onboarding first: choose your major and pathway, then come back to the OpenAI Guide."
        );
        setGuide(null);
        return;
      }
      setError(raw);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isLoggedIn) return;
    setGuide(null);
    setError(null);
    setLoading(false);
    setNeedsOnboarding(false);
  }, [isLoggedIn]);

  const citedItems = guide?.cited_checklist_item_ids
    ?.map((id) => checklistMap[id])
    .filter(Boolean) as ChecklistItem[] | undefined;

  const submitFeedback = async (helpful: boolean) => {
    if (!isLoggedIn || !guide) return;
    setFeedbackStatus(null);
    try {
      const response = await apiSend<{ ok: boolean; message: string }>(
        "/user/ai/guide/feedback",
        {
          method: "POST",
          headers: {
            ...headers,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            helpful,
            comment: feedbackComment || null,
            context_item_ids: guide.cited_checklist_item_ids ?? [],
          }),
        }
      );
      setFeedbackStatus(response.message);
      setFeedbackComment("");
    } catch (err) {
      setFeedbackStatus(err instanceof Error ? err.message : "Could not save feedback.");
    }
  };

  return (
    <section className="panel">
      <h2 className="text-3xl font-semibold">AI Guide · Powered by OpenAI</h2>
      <p className="mt-2 text-[color:var(--muted)]">
        Powered by OpenAI. Grounded recommendations based on your checklist, milestones, profile, and market signals.
      </p>
      {!isLoggedIn && (
        <p className="mt-4 text-sm text-[color:var(--accent-2)]">
          Please log in to use the OpenAI guide.
        </p>
      )}
      <div className="mt-6 grid gap-3">
        <label className="text-sm text-[color:var(--muted)]">
          Ask a specific question (optional)
          <input
            className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
            placeholder="e.g., What should I prioritize this year?"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            disabled={!isLoggedIn || loading}
          />
        </label>
        <div className="flex flex-wrap gap-3">
          <button className="cta" onClick={() => loadGuide(question)} disabled={!isLoggedIn || loading}>
            {loading ? "Generating..." : "Generate Guidance"}
          </button>
          <button
            className="cta cta-secondary"
            onClick={() => {
              setQuestion("");
              loadGuide();
            }}
            disabled={!isLoggedIn || loading}
          >
            Refresh Without Question
          </button>
        </div>
        {!guide && !loading && !error && isLoggedIn && (
          <p className="text-sm text-[color:var(--muted)]">
            Guidance is generated only after you click a button.
          </p>
        )}
        {error && (
          <p className="text-sm text-[color:var(--accent-2)]">{error}</p>
        )}
        {needsOnboarding && (
          <div className="rounded-lg border border-[color:var(--border)] p-4 text-sm text-[color:var(--muted)]">
            <a className="text-[color:var(--accent-2)] underline" href="/student/onboarding">
              Go to onboarding
            </a>{" "}
            and save your pathway selection.
          </div>
        )}
      </div>

      {guide && (
        <div className="mt-8 grid gap-6">
          <div className="rounded-xl border border-[color:var(--border)] p-5">
            <h3 className="text-xl font-semibold">Decision</h3>
            <p className="mt-2 text-[color:var(--muted)]">
              {guide.decision || "No decision provided."}
            </p>
          </div>
          <div className="rounded-xl border border-[color:var(--border)] p-5">
            <h3 className="text-xl font-semibold">Recommendations</h3>
            <ul className="mt-3 grid gap-2 text-[color:var(--muted)]">
              {guide.recommendations?.length ? (
                guide.recommendations.map((item) => <li key={item}>{item}</li>)
              ) : (
                <li>No recommendations yet.</li>
              )}
            </ul>
          </div>
          <div className="rounded-xl border border-[color:var(--border)] p-5">
            <h3 className="text-xl font-semibold">Certificates To Stand Out</h3>
            <ul className="mt-3 grid gap-2 text-[color:var(--muted)]">
              {guide.recommended_certificates?.length ? (
                guide.recommended_certificates.map((item) => <li key={item}>{item}</li>)
              ) : (
                <li>No certificate recommendations yet.</li>
              )}
            </ul>
          </div>
          <div className="rounded-xl border border-[color:var(--border)] p-5">
            <h3 className="text-xl font-semibold">Materials To Master</h3>
            <ul className="mt-3 grid gap-2 text-[color:var(--muted)]">
              {guide.materials_to_master?.length ? (
                guide.materials_to_master.map((item) => <li key={item}>{item}</li>)
              ) : (
                <li>No material guidance yet.</li>
              )}
            </ul>
          </div>
          <div className="rounded-xl border border-[color:var(--border)] p-5">
            <h3 className="text-xl font-semibold">Top Market Skills</h3>
            <ul className="mt-3 grid gap-2 text-[color:var(--muted)]">
              {guide.market_top_skills?.length ? (
                guide.market_top_skills.map((item) => <li key={item}>{item}</li>)
              ) : (
                <li>No market skills available yet.</li>
              )}
            </ul>
          </div>
          <div className="rounded-xl border border-[color:var(--border)] p-5">
            <h3 className="text-xl font-semibold">Market Alignment</h3>
            <ul className="mt-3 grid gap-2 text-[color:var(--muted)]">
              {guide.market_alignment?.length ? (
                guide.market_alignment.map((item) => <li key={item}>{item}</li>)
              ) : (
                <li>No market-alignment notes yet.</li>
              )}
            </ul>
          </div>
          <div className="rounded-xl border border-[color:var(--border)] p-5">
            <h3 className="text-xl font-semibold">Priority Focus Areas</h3>
            <ul className="mt-3 grid gap-2 text-[color:var(--muted)]">
              {guide.priority_focus_areas?.length ? (
                guide.priority_focus_areas.map((item) => <li key={item}>{item}</li>)
              ) : (
                <li>No focus areas yet.</li>
              )}
            </ul>
          </div>
          <div className="rounded-xl border border-[color:var(--border)] p-5">
            <h3 className="text-xl font-semibold">Weekly Execution Plan</h3>
            <ul className="mt-3 grid gap-2 text-[color:var(--muted)]">
              {guide.weekly_plan?.length ? (
                guide.weekly_plan.map((item) => <li key={item}>{item}</li>)
              ) : (
                <li>No weekly plan yet.</li>
              )}
            </ul>
          </div>
          <div className="rounded-xl border border-[color:var(--border)] p-5">
            <h3 className="text-xl font-semibold">Resume Improvement Areas</h3>
            {guide.resume_detected ? (
              <div className="mt-3 grid gap-4">
                <div>
                  <p className="text-sm font-medium text-white">Strengths Detected</p>
                  <ul className="mt-2 grid gap-2 text-[color:var(--muted)]">
                    {guide.resume_strengths?.length ? (
                      guide.resume_strengths.map((item) => <li key={item}>{item}</li>)
                    ) : (
                      <li>No specific strengths detected yet.</li>
                    )}
                  </ul>
                </div>
                <div>
                  <p className="text-sm font-medium text-white">What To Improve</p>
                  <ul className="mt-2 grid gap-2 text-[color:var(--muted)]">
                    {guide.resume_improvements?.length ? (
                      guide.resume_improvements.map((item) => <li key={item}>{item}</li>)
                    ) : (
                      <li>Your resume is already aligned with current checklist needs.</li>
                    )}
                  </ul>
                </div>
              </div>
            ) : (
              <p className="mt-2 text-[color:var(--muted)]">
                Upload your resume in the Profile page to get automatic resume-specific improvement feedback.
              </p>
            )}
          </div>
          <div className="rounded-xl border border-[color:var(--border)] p-5">
            <h3 className="text-xl font-semibold">Next Actions</h3>
            <ul className="mt-3 grid gap-2 text-[color:var(--muted)]">
              {guide.next_actions?.length ? (
                guide.next_actions.map((item) => <li key={item}>{item}</li>)
              ) : (
                <li>No next actions yet.</li>
              )}
            </ul>
          </div>
          <div className="rounded-xl border border-[color:var(--border)] p-5">
            <h3 className="text-xl font-semibold">Suggested Proof Types</h3>
            <div className="mt-3 flex flex-wrap gap-2">
              {guide.suggested_proof_types?.length ? (
                guide.suggested_proof_types.map((type) => (
                  <span key={type} className="chip">
                    {type}
                  </span>
                ))
              ) : (
                <span className="text-[color:var(--muted)]">
                  No proof types suggested.
                </span>
              )}
            </div>
          </div>
          <div className="rounded-xl border border-[color:var(--border)] p-5">
            <h3 className="text-xl font-semibold">Cited Checklist Items</h3>
            <ul className="mt-3 grid gap-2 text-[color:var(--muted)]">
              {citedItems?.length ? (
                citedItems.map((item) => (
                  <li key={item.id}>
                    {item.title} ({item.status})
                  </li>
                ))
              ) : (
                <li>No citations provided.</li>
              )}
            </ul>
          </div>
          <div className="rounded-xl border border-[color:var(--border)] p-5">
            <h3 className="text-xl font-semibold">Evidence + Confidence</h3>
            <ul className="mt-3 grid gap-2 text-[color:var(--muted)]">
              {guide.evidence_snippets?.length ? (
                guide.evidence_snippets.map((snippet) => <li key={snippet}>{snippet}</li>)
              ) : (
                <li>No evidence snippets yet.</li>
              )}
            </ul>
            <div className="mt-4 grid gap-2 text-sm text-[color:var(--muted)]">
              {Object.entries(guide.confidence_by_item || {}).slice(0, 10).map(([id, score]) => (
                <div key={id}>
                  {checklistMap[id]?.title ?? id}: {(score * 100).toFixed(0)}%
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-xl border border-[color:var(--border)] p-5">
            <h3 className="text-xl font-semibold">Feedback Loop</h3>
            <p className="mt-2 text-[color:var(--muted)]">
              Tell the system whether this guidance helped. Feedback is stored for model improvement.
            </p>
            <textarea
              className="mt-3 w-full rounded-lg border border-[color:var(--border)] p-3 text-sm"
              placeholder="Optional comment"
              value={feedbackComment}
              onChange={(event) => setFeedbackComment(event.target.value)}
            />
            <div className="mt-3 flex flex-wrap gap-3">
              <button className="cta cta-secondary" onClick={() => submitFeedback(true)}>
                Helpful
              </button>
              <button className="cta cta-secondary" onClick={() => submitFeedback(false)}>
                Not helpful
              </button>
            </div>
            {feedbackStatus && (
              <p className="mt-3 text-sm text-[color:var(--muted)]">{feedbackStatus}</p>
            )}
          </div>
          {guide.uncertainty && (
            <div className="rounded-xl border border-[color:var(--border)] p-5">
              <h3 className="text-xl font-semibold">Uncertainty</h3>
              <p className="mt-2 text-[color:var(--muted)]">{guide.uncertainty}</p>
            </div>
          )}
          <div className="rounded-xl border border-[color:var(--border)] p-5">
            <h3 className="text-xl font-semibold">Explanation</h3>
            <p className="mt-2 text-[color:var(--muted)]">{guide.explanation}</p>
          </div>
        </div>
      )}
    </section>
  );
}
