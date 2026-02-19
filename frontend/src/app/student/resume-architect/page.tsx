"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet, apiSend } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { AiResumeArtifact } from "@/types/api";

export default function StudentResumeArchitectPage() {
  const { username, isLoggedIn } = useSession();
  const headers = useMemo(() => ({ "X-User-Id": username }), [username]);

  const [targetRole, setTargetRole] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [artifacts, setArtifacts] = useState<AiResumeArtifact[]>([]);
  const [activeArtifact, setActiveArtifact] = useState<AiResumeArtifact | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const loadArtifacts = useCallback(() => {
    if (!isLoggedIn) return;
    apiGet<AiResumeArtifact[]>("/user/ai/resume-architect", headers)
      .then((rows) => {
        setArtifacts(rows);
        if (rows.length > 0) {
          setActiveArtifact((current) => current ?? rows[0]);
        }
      })
      .catch(() => setArtifacts([]));
  }, [headers, isLoggedIn]);

  useEffect(() => {
    loadArtifacts();
  }, [loadArtifacts]);

  const generateResume = async () => {
    if (!isLoggedIn) {
      setError("Please log in to generate a resume.");
      return;
    }
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const artifact = await apiSend<AiResumeArtifact>("/user/ai/resume-architect", {
        method: "POST",
        headers: {
          ...headers,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          target_role: targetRole.trim() || null,
          job_description: jobDescription.trim() || null,
        }),
      });
      setActiveArtifact(artifact);
      setMessage("Resume draft generated from your proof vault.");
      loadArtifacts();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not generate resume.");
    } finally {
      setLoading(false);
    }
  };

  const copyResume = async () => {
    if (!activeArtifact?.markdown_content) return;
    try {
      await navigator.clipboard.writeText(activeArtifact.markdown_content);
      setMessage("Resume markdown copied.");
    } catch {
      setError("Could not copy resume text.");
    }
  };

  return (
    <section className="panel">
      <h2 className="text-3xl font-semibold">AI Resume Architect · Powered by OpenAI</h2>
      <p className="mt-2 text-[color:var(--muted)]">
        Build ATS-optimized resumes directly from your profile and submitted proofs.
      </p>

      {!isLoggedIn && (
        <p className="mt-4 text-sm text-[color:var(--accent-2)]">
          Please log in to generate resume drafts.
        </p>
      )}
      {error && <p className="mt-4 text-sm text-[color:var(--accent-2)]">{error}</p>}
      {message && <p className="mt-4 text-sm text-[color:var(--muted)]">{message}</p>}

      <div className="mt-6 grid gap-3 md:grid-cols-2">
        <label className="text-sm text-[color:var(--muted)]" htmlFor="resume-target-role">
          Target role
          <input
            id="resume-target-role"
            className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
            value={targetRole}
            onChange={(event) => setTargetRole(event.target.value)}
            placeholder="e.g., Software Engineer Intern"
          />
        </label>
        <div className="flex items-end">
          <button className="cta w-full" onClick={generateResume} disabled={!isLoggedIn || loading}>
            {loading ? "Generating..." : "Generate Resume Draft"}
          </button>
        </div>
      </div>
      <label className="mt-3 block text-sm text-[color:var(--muted)]" htmlFor="resume-job-description">
        Job description (optional)
        <textarea
          id="resume-job-description"
          className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
          rows={5}
          value={jobDescription}
          onChange={(event) => setJobDescription(event.target.value)}
          placeholder="Paste target job description for tailored keyword alignment."
        />
      </label>

      {artifacts.length > 0 && (
        <div className="mt-8">
          <h3 className="text-xl font-semibold">Generated Drafts</h3>
          <div className="mt-3 grid gap-3">
            {artifacts.map((artifact) => (
              <button
                key={artifact.id}
                className={`rounded-xl border p-4 text-left ${
                  activeArtifact?.id === artifact.id
                    ? "border-[color:var(--accent-2)]"
                    : "border-[color:var(--border)]"
                }`}
                onClick={() => setActiveArtifact(artifact)}
              >
                <p className="font-medium">
                  {artifact.target_role || "General resume draft"}
                </p>
                <p className="text-sm text-[color:var(--muted)]">
                  {new Date(artifact.created_at).toLocaleString()}
                </p>
              </button>
            ))}
          </div>
        </div>
      )}

      {activeArtifact && (
        <div className="mt-8 rounded-xl border border-[color:var(--border)] p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="text-xl font-semibold">Resume Output</h3>
            <button className="cta cta-secondary" onClick={copyResume}>
              Copy Markdown
            </button>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {activeArtifact.ats_keywords.length ? (
              activeArtifact.ats_keywords.map((keyword) => (
                <span key={keyword} className="chip">
                  {keyword}
                </span>
              ))
            ) : (
              <span className="text-sm text-[color:var(--muted)]">
                No extracted keywords yet.
              </span>
            )}
          </div>
          <textarea
            className="mt-4 min-h-[320px] w-full rounded-lg border border-[color:var(--border)] p-3 font-mono text-sm"
            value={activeArtifact.markdown_content}
            readOnly
          />
        </div>
      )}
    </section>
  );
}
