"use client";

import { useEffect, useMemo, useState } from "react";
import { apiGet, apiSend, API_BASE } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { useSession } from "@/lib/session";
import type { Proof, ChecklistItem, RepoProofChecker, StudentProfile } from "@/types/api";

export default function StudentProofsPage() {
  const { username, isLoggedIn } = useSession();
  const headers = useMemo(() => ({ "X-User-Id": username }), [username]);
  const [proofs, setProofs] = useState<Proof[]>([]);
  const [itemMap, setItemMap] = useState<Record<string, string>>({});
  const [targetJob, setTargetJob] = useState("software engineer");
  const [location, setLocation] = useState("united states");
  const [repoUrl, setRepoUrl] = useState("");
  const [verifyingProofId, setVerifyingProofId] = useState<string | null>(null);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoggedIn) return;
    setError(null);
    setSyncMessage(null);
    apiGet<Proof[]>("/user/proofs", headers)
      .then(setProofs)
      .catch(() => setError("Unable to load proofs."));
    apiGet<ChecklistItem[]>("/user/checklist", headers)
      .then((items) => {
        const map: Record<string, string> = {};
        items.forEach((item) => {
          map[item.id] = item.title;
        });
        setItemMap(map);
      })
      .catch(() => setItemMap({}));
    apiGet<StudentProfile>("/user/profile", headers)
      .then((profile) => {
        if (profile.github_username) {
          setRepoUrl(`https://github.com/${profile.github_username}`);
        }
        if (profile.state) {
          setLocation(profile.state);
        }
      })
      .catch(() => null);
  }, [headers, isLoggedIn]);

  const verifyProofWithRepo = async (proofId: string) => {
    if (!isLoggedIn) {
      setError("Please log in to verify proofs by repo.");
      return;
    }
    if (!repoUrl.trim()) {
      setError("Enter a GitHub URL before running repo verification.");
      return;
    }

    setVerifyingProofId(proofId);
    setError(null);
    setSyncMessage(null);
    try {
      const result = await apiSend<RepoProofChecker>("/user/ai/proof-checker", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({
          target_job: targetJob.trim() || "software engineer",
          location: location.trim() || "united states",
          repo_url: repoUrl.trim(),
          proof_id: proofId,
        }),
      });
      setSyncMessage(
        `Repo sync complete: ${result.match_count}/${result.required_skills_count} required skills matched by code.`
      );
      const refreshed = await apiGet<Proof[]>("/user/proofs", headers);
      setProofs(refreshed);
    } catch (err) {
      setError(getErrorMessage(err) || "Repo verification failed.");
    } finally {
      setVerifyingProofId(null);
    }
  };

  const prettyProofType = (proofTypeValue: string) => {
    if (proofTypeValue === "resume_upload_match") return "resume upload match";
    return proofTypeValue.replace(/_/g, " ");
  };

  const prettyStatus = (status: string) => {
    if (status === "submitted") return "waiting for verification";
    if (status === "needs_more_evidence") return "needs more evidence";
    return status.replace(/_/g, " ");
  };

  return (
    <section className="panel">
      <h2 className="text-3xl font-semibold">My Proofs</h2>
      <p className="mt-2 text-[color:var(--muted)]">
        Track verification status, review notes, and repo-verified skill evidence.
      </p>
      {!isLoggedIn && (
        <p className="mt-4 text-sm text-[color:var(--accent-2)]">
          Please log in to view your proofs.
        </p>
      )}
      {error && (
        <p className="mt-4 text-sm text-[color:var(--accent-2)]">{error}</p>
      )}
      {syncMessage && (
        <p className="mt-4 text-sm text-emerald-300">{syncMessage}</p>
      )}

      <div className="mt-5 rounded-xl border border-[color:var(--border)] p-4">
        <p className="text-sm font-semibold text-white">GitHub Skill Sync</p>
        <p className="mt-1 text-xs text-[color:var(--muted)]">
          Link your repo and verify each proof against live CareerOneStop skill standards.
        </p>
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          <input
            className="rounded-lg border border-[color:var(--border)] p-3"
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
            placeholder="https://github.com/owner or /owner/repo"
          />
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
        </div>
      </div>

      <div className="mt-6 grid gap-3">
        {proofs.length === 0 && isLoggedIn && (
          <div className="text-sm text-[color:var(--muted)]">
            No proofs submitted yet.
          </div>
        )}
        {proofs.map((proof) => (
          <div key={proof.id} className="rounded-xl border border-[color:var(--border)] p-5">
            <div className="flex flex-col gap-1">
              <p className="text-sm text-[color:var(--muted)]">
                {itemMap[proof.checklist_item_id] ?? "Checklist item"}
              </p>
              <p className="text-lg font-semibold">
                {prettyProofType(proof.proof_type)} - {prettyStatus(proof.status)}
              </p>
              <a
                className="text-sm text-[color:var(--accent-2)] underline"
                href={
                  (proof.view_url || proof.url).startsWith("http")
                    ? proof.view_url || proof.url
                    : `${API_BASE}${proof.view_url || proof.url}`
                }
                target="_blank"
                rel="noreferrer"
              >
                {proof.url}
              </a>
              {(() => {
                const metadata = proof.metadata && typeof proof.metadata === "object" ? proof.metadata : {};
                const repoVerified = Boolean((metadata as Record<string, unknown>).repo_verified);
                const rawMatched = (metadata as Record<string, unknown>).repo_matched_skills;
                const matchedSkills =
                  Array.isArray(rawMatched) ? rawMatched.map((value) => String(value).trim()).filter(Boolean) : [];
                const confidenceValue = (metadata as Record<string, unknown>).repo_confidence;
                const repoConfidence = typeof confidenceValue === "number" ? confidenceValue : null;

                if (!repoVerified && matchedSkills.length === 0 && repoConfidence === null) return null;

                return (
                  <div className="mt-2 rounded-lg border border-white/10 bg-black/20 p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs ${
                          repoVerified
                            ? "border border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                            : "border border-amber-500/40 bg-amber-500/10 text-amber-300"
                        }`}
                      >
                        {repoVerified ? "Verified by Repo" : "Repo Checked"}
                      </span>
                      {repoConfidence !== null && (
                        <span className="text-xs text-[color:var(--muted)]">
                          Confidence: {repoConfidence.toFixed(1)}%
                        </span>
                      )}
                    </div>
                    {matchedSkills.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {matchedSkills.slice(0, 8).map((skill) => (
                          <span
                            key={`${proof.id}-${skill}`}
                            className="rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2 py-0.5 text-xs text-emerald-300"
                          >
                            {skill}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })()}
              {proof.review_note && (
                <p className="mt-2 text-sm text-[color:var(--muted)]">
                  Admin note: {proof.review_note}
                </p>
              )}
              <div className="mt-3">
                <button
                  className="cta cta-secondary"
                  onClick={() => verifyProofWithRepo(proof.id)}
                  disabled={!repoUrl.trim() || verifyingProofId === proof.id}
                >
                  {verifyingProofId === proof.id ? "Verifying..." : "Verify by Repo"}
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
