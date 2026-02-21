"use client";

import { useEffect, useMemo, useState } from "react";
import { apiGet, apiSend } from "@/lib/api";
import { getErrorMessage, getRetryAfterSeconds, isRateLimited } from "@/lib/errors";
import { useSession } from "@/lib/session";
import type { ChecklistItem, AiGuide } from "@/types/api";

type AiIfIWereYouOut = {
  summary: string;
  fastest_path: string[];
  realistic_next_moves: string[];
  avoid_now: string[];
  recommended_certificates: string[];
  uncertainty?: string | null;
};

type AiEmotionalResetOut = {
  title: string;
  story: string;
  reframe: string;
  action_plan: string[];
  uncertainty?: string | null;
};

type AiRebuildPlanOut = {
  summary: string;
  day_0_30: string[];
  day_31_60: string[];
  day_61_90: string[];
  weekly_targets: string[];
  portfolio_targets: string[];
  recommended_certificates: string[];
  uncertainty?: string | null;
};

type AiCollegeGapOut = {
  job_description_playbook: string[];
  reverse_engineer_skills: string[];
  project_that_recruiters_care: string[];
  networking_strategy: string[];
  uncertainty?: string | null;
};

export default function StudentAiGuidePage() {
  const { username, isLoggedIn } = useSession();
  const headers = useMemo(() => ({ "X-User-Id": username }), [username]);
  const [question, setQuestion] = useState("");
  const [guide, setGuide] = useState<AiGuide | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [checklistMap, setChecklistMap] = useState<Record<string, ChecklistItem>>(
    {}
  );
  const [feedbackComment, setFeedbackComment] = useState("");
  const [feedbackStatus, setFeedbackStatus] = useState<string | null>(null);
  const [ifGpa, setIfGpa] = useState("");
  const [ifInternship, setIfInternship] = useState("");
  const [ifIndustry, setIfIndustry] = useState("");
  const [ifLocation, setIfLocation] = useState("");
  const [ifResult, setIfResult] = useState<AiIfIWereYouOut | null>(null);
  const [ifLoading, setIfLoading] = useState(false);
  const [ifError, setIfError] = useState<string | null>(null);
  const [emotionalContext, setEmotionalContext] = useState("");
  const [emotionalResult, setEmotionalResult] = useState<AiEmotionalResetOut | null>(null);
  const [emotionalLoading, setEmotionalLoading] = useState(false);
  const [emotionalError, setEmotionalError] = useState<string | null>(null);
  const [planSkills, setPlanSkills] = useState("");
  const [planTargetJob, setPlanTargetJob] = useState("");
  const [planLocation, setPlanLocation] = useState("");
  const [planHours, setPlanHours] = useState("8");
  const [planResult, setPlanResult] = useState<AiRebuildPlanOut | null>(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [planError, setPlanError] = useState<string | null>(null);
  const [gapTargetJob, setGapTargetJob] = useState("");
  const [gapCurrentSkills, setGapCurrentSkills] = useState("");
  const [gapResult, setGapResult] = useState<AiCollegeGapOut | null>(null);
  const [gapLoading, setGapLoading] = useState(false);
  const [gapError, setGapError] = useState<string | null>(null);

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
      if (isRateLimited(err)) {
        const retry = getRetryAfterSeconds(err);
        setError(
          retry
            ? `Rate limit reached. Try again in about ${retry} seconds.`
            : "Rate limit reached. Please wait and try again."
        );
      } else {
        setError(getErrorMessage(err) || "Failed to load OpenAI guidance.");
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isLoggedIn) return;
    setGuide(null);
    setError(null);
    setLoading(false);
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

  const runIfIWereYou = async () => {
    if (!isLoggedIn) {
      setIfError("Please log in to use this service.");
      return;
    }
    setIfLoading(true);
    setIfError(null);
    try {
      const parsedGpa = ifGpa.trim() ? Number(ifGpa) : null;
      const data = await apiSend<AiIfIWereYouOut>("/user/ai/if-i-were-you", {
        method: "POST",
        headers: {
          ...headers,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          gpa: parsedGpa !== null && Number.isFinite(parsedGpa) ? parsedGpa : null,
          internship_history: ifInternship.trim() || null,
          industry: ifIndustry.trim() || null,
          location: ifLocation.trim() || null,
        }),
      });
      setIfResult(data);
    } catch (err) {
      setIfError(getErrorMessage(err) || "Service unavailable.");
    } finally {
      setIfLoading(false);
    }
  };

  const runEmotionalReset = async () => {
    if (!isLoggedIn) {
      setEmotionalError("Please log in to use this service.");
      return;
    }
    setEmotionalLoading(true);
    setEmotionalError(null);
    try {
      const data = await apiSend<AiEmotionalResetOut>("/user/ai/emotional-reset", {
        method: "POST",
        headers: {
          ...headers,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          story_context: emotionalContext.trim() || null,
        }),
      });
      setEmotionalResult(data);
    } catch (err) {
      setEmotionalError(getErrorMessage(err) || "Service unavailable.");
    } finally {
      setEmotionalLoading(false);
    }
  };

  const runRebuildPlan = async () => {
    if (!isLoggedIn) {
      setPlanError("Please log in to use this service.");
      return;
    }
    if (!planSkills.trim() || !planTargetJob.trim()) {
      setPlanError("Current skills and target job are required.");
      return;
    }
    setPlanLoading(true);
    setPlanError(null);
    try {
      const parsedHours = Number(planHours);
      const data = await apiSend<AiRebuildPlanOut>("/user/ai/rebuild-90-day", {
        method: "POST",
        headers: {
          ...headers,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          current_skills: planSkills.trim(),
          target_job: planTargetJob.trim(),
          location: planLocation.trim() || null,
          hours_per_week: Number.isFinite(parsedHours) ? parsedHours : 8,
        }),
      });
      setPlanResult(data);
    } catch (err) {
      setPlanError(getErrorMessage(err) || "Service unavailable.");
    } finally {
      setPlanLoading(false);
    }
  };

  const runCollegeGap = async () => {
    if (!isLoggedIn) {
      setGapError("Please log in to use this service.");
      return;
    }
    setGapLoading(true);
    setGapError(null);
    try {
      const data = await apiSend<AiCollegeGapOut>("/user/ai/college-gap-playbook", {
        method: "POST",
        headers: {
          ...headers,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          target_job: gapTargetJob.trim() || null,
          current_skills: gapCurrentSkills.trim() || null,
        }),
      });
      setGapResult(data);
    } catch (err) {
      setGapError(getErrorMessage(err) || "Service unavailable.");
    } finally {
      setGapLoading(false);
    }
  };

  return (
    <section className="panel">
      <h2 className="text-3xl font-semibold">AI Career Services</h2>
      <p className="mt-2 text-[color:var(--muted)]">
        This tab combines targeted guidance, practical recovery support, and structured execution planning to help you move faster toward the right role.
      </p>
      <div className="mt-4 rounded-xl border border-[color:var(--border)] p-4 text-sm text-[color:var(--muted)]">
        <p>What you can do here:</p>
        <ul className="mt-2 grid gap-1">
          <li>Get direct guidance from your current checklist and profile context.</li>
          <li>Use If I Were You Mode for realistic next moves based on your background.</li>
          <li>Use Graduated But Feel Behind for emotional reset plus practical actions.</li>
          <li>Generate a 90-Day Rebuild Plan with weekly execution targets.</li>
          <li>Use College Didn&apos;t Teach Me This for job-description and networking playbooks.</li>
        </ul>
      </div>
      {!isLoggedIn && (
        <p className="mt-4 text-sm text-[color:var(--accent-2)]">
          Please log in to use AI Career Services.
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

      <div className="mt-8 grid gap-6">
        <div className="rounded-xl border border-[color:var(--border)] p-5">
          <h3 className="text-xl font-semibold">If I Were You Mode</h3>
          <p className="mt-2 text-[color:var(--muted)]">
            Realistic next moves based on GPA, internship history, industry, and location.
          </p>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <input className="rounded-lg border border-[color:var(--border)] p-3" type="number" min={0} max={4} step="0.01" placeholder="GPA (optional)" value={ifGpa} onChange={(e) => setIfGpa(e.target.value)} />
            <input className="rounded-lg border border-[color:var(--border)] p-3" placeholder="Target industry" value={ifIndustry} onChange={(e) => setIfIndustry(e.target.value)} />
            <textarea className="rounded-lg border border-[color:var(--border)] p-3 md:col-span-2" placeholder="Internship history" value={ifInternship} onChange={(e) => setIfInternship(e.target.value)} />
            <input className="rounded-lg border border-[color:var(--border)] p-3" placeholder="Location" value={ifLocation} onChange={(e) => setIfLocation(e.target.value)} />
          </div>
          <div className="mt-3">
            <button className="cta" onClick={runIfIWereYou} disabled={!isLoggedIn || ifLoading}>{ifLoading ? "Generating..." : "Generate My Path"}</button>
          </div>
          {ifError && <p className="mt-3 text-sm text-[color:var(--accent-2)]">{ifError}</p>}
          {ifResult && (
            <div className="mt-4 grid gap-3 text-[color:var(--muted)]">
              <p><span className="font-semibold text-white">Summary:</span> {ifResult.summary}</p>
              <p className="font-semibold text-white">Fastest Path</p>
              <ul className="grid gap-1">{ifResult.fastest_path.map((item) => <li key={item}>{item}</li>)}</ul>
              <p className="font-semibold text-white">Realistic Next Moves</p>
              <ul className="grid gap-1">{ifResult.realistic_next_moves.map((item) => <li key={item}>{item}</li>)}</ul>
            </div>
          )}
        </div>

        <div className="rounded-xl border border-[color:var(--border)] p-5">
          <h3 className="text-xl font-semibold">Graduated But Feel Behind?</h3>
          <p className="mt-2 text-[color:var(--muted)]">Get structured emotional reset plus action-oriented direction.</p>
          <textarea className="mt-4 w-full rounded-lg border border-[color:var(--border)] p-3" placeholder="Share your current situation (optional)" value={emotionalContext} onChange={(e) => setEmotionalContext(e.target.value)} />
          <div className="mt-3">
            <button className="cta" onClick={runEmotionalReset} disabled={!isLoggedIn || emotionalLoading}>{emotionalLoading ? "Generating..." : "Generate Reset Plan"}</button>
          </div>
          {emotionalError && <p className="mt-3 text-sm text-[color:var(--accent-2)]">{emotionalError}</p>}
          {emotionalResult && (
            <div className="mt-4 grid gap-2 text-[color:var(--muted)]">
              <p className="font-semibold text-white">{emotionalResult.title}</p>
              <p>{emotionalResult.story}</p>
              <p><span className="font-semibold text-white">Reframe:</span> {emotionalResult.reframe}</p>
              <ul className="grid gap-1">{emotionalResult.action_plan.map((item) => <li key={item}>{item}</li>)}</ul>
            </div>
          )}
        </div>

        <div className="rounded-xl border border-[color:var(--border)] p-5">
          <h3 className="text-xl font-semibold">90-Day Rebuild Plan Generator</h3>
          <p className="mt-2 text-[color:var(--muted)]">Create a practical 90-day plan from your current skills and target role.</p>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <textarea className="rounded-lg border border-[color:var(--border)] p-3 md:col-span-2" placeholder="Current skills" value={planSkills} onChange={(e) => setPlanSkills(e.target.value)} />
            <input className="rounded-lg border border-[color:var(--border)] p-3" placeholder="Target job" value={planTargetJob} onChange={(e) => setPlanTargetJob(e.target.value)} />
            <input className="rounded-lg border border-[color:var(--border)] p-3" placeholder="Location" value={planLocation} onChange={(e) => setPlanLocation(e.target.value)} />
            <input className="rounded-lg border border-[color:var(--border)] p-3" type="number" min={1} max={80} placeholder="Hours per week" value={planHours} onChange={(e) => setPlanHours(e.target.value)} />
          </div>
          <div className="mt-3">
            <button className="cta" onClick={runRebuildPlan} disabled={!isLoggedIn || planLoading}>{planLoading ? "Building..." : "Generate 90-Day Plan"}</button>
          </div>
          {planError && <p className="mt-3 text-sm text-[color:var(--accent-2)]">{planError}</p>}
          {planResult && (
            <div className="mt-4 grid gap-2 text-[color:var(--muted)]">
              <p className="font-semibold text-white">Summary</p>
              <p>{planResult.summary}</p>
            </div>
          )}
        </div>

        <div className="rounded-xl border border-[color:var(--border)] p-5">
          <h3 className="text-xl font-semibold">College Didn&apos;t Teach Me This</h3>
          <p className="mt-2 text-[color:var(--muted)]">Generate practical playbooks for job descriptions, project strategy, and networking.</p>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <input className="rounded-lg border border-[color:var(--border)] p-3" placeholder="Target job" value={gapTargetJob} onChange={(e) => setGapTargetJob(e.target.value)} />
            <input className="rounded-lg border border-[color:var(--border)] p-3" placeholder="Current skills" value={gapCurrentSkills} onChange={(e) => setGapCurrentSkills(e.target.value)} />
          </div>
          <div className="mt-3">
            <button className="cta" onClick={runCollegeGap} disabled={!isLoggedIn || gapLoading}>{gapLoading ? "Generating..." : "Generate Playbook"}</button>
          </div>
          {gapError && <p className="mt-3 text-sm text-[color:var(--accent-2)]">{gapError}</p>}
          {gapResult && (
            <div className="mt-4 grid gap-2 text-[color:var(--muted)]">
              <p className="font-semibold text-white">How To Read Job Descriptions</p>
              <ul className="grid gap-1">{gapResult.job_description_playbook.map((item) => <li key={item}>{item}</li>)}</ul>
            </div>
          )}
        </div>

        <p className="text-sm text-[color:var(--muted)]">
          All services in this tab are powered by OpenAI.
        </p>
      </div>
    </section>
  );
}
