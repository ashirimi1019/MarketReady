"use client";

import { useEffect, useMemo, useState } from "react";
import { apiGet, apiSend, API_BASE, getAuthHeaders } from "@/lib/api";
import { useSession } from "@/lib/session";

type StudentProfile = {
  semester?: string | null;
  state?: string | null;
  university?: string | null;
  masters_interest?: boolean;
  masters_target?: string | null;
  masters_timeline?: string | null;
  masters_status?: string | null;
  github_username?: string | null;
  resume_url?: string | null;
  resume_view_url?: string | null;
  resume_filename?: string | null;
  resume_uploaded_at?: string | null;
};

type ChecklistItem = {
  id: string;
  status: string;
};

type Readiness = {
  score: number;
  band: string;
};

export default function StudentProfilePage() {
  const { username, isLoggedIn } = useSession();
  const headers = useMemo(() => ({ "X-User-Id": username }), [username]);

  const [semester, setSemester] = useState("");
  const [state, setState] = useState("");
  const [university, setUniversity] = useState("");
  const [githubUsername, setGithubUsername] = useState("");
  const [mastersInterest, setMastersInterest] = useState(false);
  const [mastersTarget, setMastersTarget] = useState("");
  const [mastersTimeline, setMastersTimeline] = useState("");
  const [mastersStatus, setMastersStatus] = useState("");
  const [resumeUrl, setResumeUrl] = useState<string | null>(null);
  const [resumeViewUrl, setResumeViewUrl] = useState<string | null>(null);
  const [resumeFilename, setResumeFilename] = useState<string | null>(null);
  const [resumeUploadedAt, setResumeUploadedAt] = useState<string | null>(null);
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [uploadingResume, setUploadingResume] = useState(false);
  const [deletingResume, setDeletingResume] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!isLoggedIn) return;
    apiGet<StudentProfile>("/user/profile", headers)
      .then((data) => {
        setSemester(data.semester ?? "");
        setState(data.state ?? "");
        setUniversity(data.university ?? "");
        setGithubUsername(data.github_username ?? "");
        setMastersInterest(Boolean(data.masters_interest));
        setMastersTarget(data.masters_target ?? "");
        setMastersTimeline(data.masters_timeline ?? "");
        setMastersStatus(data.masters_status ?? "");
        setResumeUrl(data.resume_url ?? null);
        setResumeViewUrl(data.resume_view_url ?? null);
        setResumeFilename(data.resume_filename ?? null);
        setResumeUploadedAt(data.resume_uploaded_at ?? null);
      })
      .catch(() => {
        // profile may not exist yet
      });
  }, [headers, isLoggedIn]);

  const saveProfile = async () => {
    if (!isLoggedIn) {
      setMessage("Please log in to save your profile.");
      return;
    }
    setMessage(null);
    setSaving(true);
    try {
      await apiSend("/user/profile", {
        method: "PUT",
        headers: {
          ...headers,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          semester,
          state,
          university,
          masters_interest: mastersInterest,
          masters_target: mastersTarget || null,
          masters_timeline: mastersTimeline || null,
          masters_status: mastersStatus || null,
          github_username: githubUsername || null,
        }),
      });
      setMessage("Profile saved.");
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Failed to save profile."
      );
    } finally {
      setSaving(false);
    }
  };

  const uploadResume = async () => {
    if (!isLoggedIn) {
      setMessage("Please log in to upload your resume.");
      return;
    }
    if (!resumeFile) {
      setMessage("Choose a resume file first.");
      return;
    }

    setMessage(null);
    setUploadingResume(true);
    try {
      const form = new FormData();
      form.append("file", resumeFile);
      const response = await fetch(`${API_BASE}/user/profile/resume`, {
        method: "POST",
        headers: getAuthHeaders(headers),
        body: form,
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(`Resume upload failed: ${text}`);
      }
      const data = (await response.json()) as StudentProfile;
      setResumeUrl(data.resume_url ?? null);
      setResumeViewUrl(data.resume_view_url ?? null);
      setResumeFilename(data.resume_filename ?? null);
      setResumeUploadedAt(data.resume_uploaded_at ?? null);
      setResumeFile(null);
      const [checklist, readiness] = await Promise.all([
        apiGet<ChecklistItem[]>("/user/checklist", headers).catch(() => []),
        apiGet<Readiness>("/user/readiness", headers).catch(() => null),
      ]);
      const resumeSatisfiedCount = checklist.filter(
        (item) => item.status === "satisfied by resume upload"
      ).length;
      const readinessText = readiness
        ? ` Readiness updated to ${readiness.score.toFixed(0)}/100 (${readiness.band}).`
        : "";
      setMessage(
        `Resume uploaded and saved to your account.${resumeSatisfiedCount > 0 ? ` ${resumeSatisfiedCount} requirement(s) were auto-satisfied from resume evidence.` : ""}${readinessText}`
      );
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Failed to upload resume."
      );
    } finally {
      setUploadingResume(false);
    }
  };

  const removeResume = async () => {
    if (!isLoggedIn) {
      setMessage("Please log in to manage your resume.");
      return;
    }
    if (!resumeUrl) {
      setMessage("No resume is currently saved.");
      return;
    }

    setMessage(null);
    setDeletingResume(true);
    try {
      const response = await fetch(`${API_BASE}/user/profile/resume`, {
        method: "DELETE",
        headers: getAuthHeaders(headers),
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(`Resume removal failed: ${text}`);
      }

      const data = (await response.json()) as StudentProfile;
      setResumeUrl(data.resume_url ?? null);
      setResumeViewUrl(data.resume_view_url ?? null);
      setResumeFilename(data.resume_filename ?? null);
      setResumeUploadedAt(data.resume_uploaded_at ?? null);
      setResumeFile(null);
      setMessage("Resume removed. AI guidance will now use profile + entered context.");
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Failed to remove resume."
      );
    } finally {
      setDeletingResume(false);
    }
  };

  return (
    <section className="panel">
      <h2 className="text-3xl font-semibold">My Profile</h2>
      <p className="mt-2 text-[color:var(--muted)]">
        Keep your academic context up to date so your guidance stays relevant.
      </p>
      {!isLoggedIn && (
        <p className="mt-4 text-sm text-[color:var(--accent-2)]">
          Please log in to edit your profile.
        </p>
      )}
      <div className="mt-6 grid gap-4">
        <div className="rounded-xl border border-[color:var(--border)] p-5">
          <h3 className="text-lg font-semibold">Academic Details</h3>
          <div className="mt-4 grid gap-3">
            <label className="text-sm text-[color:var(--muted)]">
              Current Year
              <input
                className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
                placeholder="e.g., Year 2 (Sophomore)"
                value={semester}
                onChange={(event) => setSemester(event.target.value)}
                disabled={!isLoggedIn || saving}
              />
            </label>
            <label className="text-sm text-[color:var(--muted)]">
              State
              <input
                className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
                placeholder="e.g., Virginia"
                value={state}
                onChange={(event) => setState(event.target.value)}
                disabled={!isLoggedIn || saving}
              />
            </label>
            <label className="text-sm text-[color:var(--muted)]">
              University
              <input
                className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
                placeholder="e.g., George Mason University"
                value={university}
                onChange={(event) => setUniversity(event.target.value)}
                disabled={!isLoggedIn || saving}
              />
            </label>
            <label className="text-sm text-[color:var(--muted)]">
              GitHub Username
              <input
                className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
                placeholder="e.g., octocat"
                value={githubUsername}
                onChange={(event) => setGithubUsername(event.target.value)}
                disabled={!isLoggedIn || saving}
              />
            </label>
          </div>
        </div>

        <div className="rounded-xl border border-[color:var(--border)] p-5">
          <h3 className="text-lg font-semibold">Masters Degree Plans</h3>
          <p className="mt-2 text-sm text-[color:var(--muted)]">
            If you are approaching a Masters degree, tell us your intent so we
            can shape recommendations.
          </p>
          <div className="mt-4 grid gap-3">
            <label className="flex items-center gap-2 text-sm text-[color:var(--muted)]">
              <input
                type="checkbox"
                checked={mastersInterest}
                onChange={(event) => setMastersInterest(event.target.checked)}
                disabled={!isLoggedIn || saving}
              />
              I am approaching a Masters degree
            </label>
            <label className="text-sm text-[color:var(--muted)]">
              Target Program
              <input
                className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
                placeholder="e.g., MS in Data Science"
                value={mastersTarget}
                onChange={(event) => setMastersTarget(event.target.value)}
                disabled={!isLoggedIn || saving || !mastersInterest}
              />
            </label>
            <label className="text-sm text-[color:var(--muted)]">
              Timeline
              <input
                className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
                placeholder="e.g., Fall 2027 start"
                value={mastersTimeline}
                onChange={(event) => setMastersTimeline(event.target.value)}
                disabled={!isLoggedIn || saving || !mastersInterest}
              />
            </label>
            <label className="text-sm text-[color:var(--muted)]">
              Status
              <input
                className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
                placeholder="e.g., Considering / Applying / Accepted"
                value={mastersStatus}
                onChange={(event) => setMastersStatus(event.target.value)}
                disabled={!isLoggedIn || saving || !mastersInterest}
              />
            </label>
          </div>
        </div>

        <div className="rounded-xl border border-[color:var(--border)] p-5">
          <h3 className="text-lg font-semibold">Resume for AI Personalization - Powered by OpenAI</h3>
          <p className="mt-2 text-sm text-[color:var(--muted)]">
            Upload your resume so OpenAI can tailor recommendations to your actual experience.
          </p>
          <ul className="mt-3 list-disc pl-5 text-sm text-[color:var(--muted)]">
            <li>Career AI: role targeting and next-step recommendations.</li>
            <li>Interview AI: more relevant prompts and feedback.</li>
            <li>Resume AI: stronger keyword and impact alignment.</li>
          </ul>
          <div className="mt-4 grid gap-3">
            {resumeUrl && (
              <div className="rounded-lg border border-dashed border-[color:var(--border)] p-3 text-sm text-[color:var(--muted)]">
                <div>Current resume: {resumeFilename ?? "Uploaded resume"}</div>
                {resumeUploadedAt && (
                  <div>Uploaded at: {new Date(resumeUploadedAt).toLocaleString()}</div>
                )}
                <a
                  className="text-[color:var(--accent-2)] underline"
                  href={
                    (resumeViewUrl || resumeUrl).startsWith("http")
                      ? resumeViewUrl || resumeUrl
                      : `${API_BASE}${resumeViewUrl || resumeUrl}`
                  }
                  target="_blank"
                  rel="noreferrer"
                >
                  View resume file
                </a>
              </div>
            )}
            <label
              htmlFor="profile-resume-upload"
              className="text-sm text-[color:var(--muted)]"
            >
              Resume file
              <input
                id="profile-resume-upload"
                type="file"
                accept=".pdf,.doc,.docx,.txt,.rtf"
                className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
                title="Upload resume file"
                aria-label="Upload resume file"
                onChange={(event) => setResumeFile(event.target.files?.[0] ?? null)}
                disabled={!isLoggedIn || uploadingResume || deletingResume || saving}
              />
            </label>
            <button
              className="cta cta-secondary"
              onClick={uploadResume}
              disabled={!isLoggedIn || uploadingResume || deletingResume || saving}
            >
              {uploadingResume ? "Uploading resume..." : resumeUrl ? "Replace Resume" : "Upload Resume"}
            </button>
            {resumeUrl && (
              <button
                className="cta cta-secondary"
                onClick={removeResume}
                disabled={!isLoggedIn || uploadingResume || deletingResume || saving}
              >
                {deletingResume ? "Removing resume..." : "Remove Resume"}
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <button
          className="cta"
          onClick={saveProfile}
          disabled={!isLoggedIn || saving}
        >
          {saving ? "Saving..." : "Save Profile"}
        </button>
        {message && (
          <span className="text-sm text-[color:var(--muted)]">{message}</span>
        )}
      </div>
    </section>
  );
}
