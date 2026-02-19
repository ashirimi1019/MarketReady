"use client";

import { useEffect, useMemo, useState } from "react";
import { apiGet, apiSend } from "@/lib/api";
import { useSession } from "@/lib/session";

type Major = {
  id: string;
  name: string;
  description?: string | null;
};

type Pathway = {
  id: string;
  name: string;
  description?: string | null;
  is_compatible: boolean;
  notes?: string | null;
};

type UserPathway = {
  major_id: string;
  pathway_id: string;
  cohort?: string | null;
};

export default function StudentOnboardingPage() {
  const { username, isLoggedIn } = useSession();
  const [majors, setMajors] = useState<Major[]>([]);
  const [pathways, setPathways] = useState<Pathway[]>([]);
  const [selectedMajor, setSelectedMajor] = useState<string>("");
  const [selectedPathway, setSelectedPathway] = useState<string>("");
  const [cohort, setCohort] = useState("Fall 2026");
  const [message, setMessage] = useState<string | null>(null);
  const [locked, setLocked] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    apiGet<Major[]>("/majors")
      .then(setMajors)
      .catch(() => setMajors([]));
  }, []);

  useEffect(() => {
    if (!isLoggedIn) return;
    const selectionKey = `mp_selection_${username}`;
    const stored = window.localStorage.getItem(selectionKey);
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        if (parsed?.major_id && parsed?.pathway_id) {
          setSelectedMajor(parsed.major_id);
          setSelectedPathway(parsed.pathway_id);
          if (parsed.cohort) {
            setCohort(parsed.cohort);
          }
          setLocked(true);
        }
      } catch {
        // ignore
      }
    }

    apiGet<UserPathway>(`/user/pathway`, { "X-User-Id": username })
      .then((data) => {
        if (data?.major_id && data?.pathway_id) {
          setSelectedMajor(data.major_id);
          setSelectedPathway(data.pathway_id);
          if (data.cohort) {
            setCohort(data.cohort);
          }
          setLocked(true);
          window.localStorage.setItem(
            selectionKey,
            JSON.stringify({
              major_id: data.major_id,
              pathway_id: data.pathway_id,
              cohort: data.cohort,
            })
          );
        }
      })
      .catch(async () => {
        if (stored) {
          try {
            const parsed = JSON.parse(stored);
            if (parsed?.major_id && parsed?.pathway_id) {
              await apiSend("/user/pathway/select", {
                method: "POST",
                headers: {
                  "X-User-Id": username,
                  "Content-Type": "application/json",
                },
                body: JSON.stringify(parsed),
              });
              setLocked(true);
              setMessage("Selection restored and locked.");
              return;
            }
          } catch {
            // ignore
          }
        }
        setLocked(false);
      });
  }, [isLoggedIn, username]);


  useEffect(() => {
    if (!selectedMajor) {
      setPathways([]);
      return;
    }
    apiGet<Pathway[]>(`/majors/${selectedMajor}/pathways`)
      .then(setPathways)
      .catch(() => setPathways([]));
  }, [selectedMajor]);

  const headers = useMemo(() => ({ "X-User-Id": username }), [username]);

  const submitSelection = async () => {
    if (!selectedMajor || !selectedPathway) {
      setMessage("Select a major and pathway first.");
      return;
    }
    if (locked) {
      setMessage("Selection is locked.");
      return;
    }
    setMessage(null);
    setSaving(true);
    try {
      await apiSend("/user/pathway/select", {
        method: "POST",
        headers: {
          ...headers,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          major_id: selectedMajor,
          pathway_id: selectedPathway,
          cohort,
        }),
      });
      const saved = await apiGet<UserPathway>("/user/pathway", headers);
      if (saved?.major_id && saved?.pathway_id) {
        setSelectedMajor(saved.major_id);
        setSelectedPathway(saved.pathway_id);
        setLocked(true);
        setMessage("Selection saved and locked.");
        window.localStorage.setItem(
          `mp_selection_${username}`,
          JSON.stringify({
            major_id: saved.major_id,
            pathway_id: saved.pathway_id,
            cohort: saved.cohort,
          })
        );
      } else {
        setMessage("Saved, but could not verify selection.");
      }
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Failed to save selection."
      );
    } finally {
      setSaving(false);
    }
  };


  return (
    <section className="panel">
      <h2 className="text-2xl font-semibold">Choose Your Major</h2>
      <p className="mt-2 text-[color:var(--muted)]">
        Select your major to unlock compatible pathways.
      </p>
      <div className="mt-6 grid gap-4">
        <div className="rounded-lg border border-dashed border-[color:var(--border)] p-4 text-sm text-[color:var(--muted)]">
          {isLoggedIn
            ? `Logged in as ${username}. Your selections will be saved to this account.`
            : "You must log in to save a pathway selection."}
        </div>
        {locked && (
          <div className="rounded-lg border border-dashed border-[color:var(--border)] p-4 text-sm text-[color:var(--accent-2)]">
            Selection is locked. Contact admin to change your pathway.
          </div>
        )}
        <label className="text-sm text-[color:var(--muted)]">
          Cohort
          <input
            className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
            value={cohort}
            onChange={(event) => setCohort(event.target.value)}
            disabled={!isLoggedIn || locked}
          />
        </label>
      </div>
      <div className="mt-6 grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-[color:var(--border)] p-5">
          <h3 className="text-lg font-semibold">Major</h3>
          <select
            className="mt-3 w-full rounded-lg border border-[color:var(--border)] p-3"
            value={selectedMajor}
            onChange={(event) => setSelectedMajor(event.target.value)}
            disabled={!isLoggedIn || locked}
          >
            <option value="">Select a major</option>
            {majors.map((major) => (
              <option key={major.id} value={major.id}>
                {major.name}
              </option>
            ))}
          </select>
        </div>
        <div className="rounded-xl border border-[color:var(--border)] p-5">
          <h3 className="text-lg font-semibold">Pathway</h3>
          <select
            className="mt-3 w-full rounded-lg border border-[color:var(--border)] p-3"
            value={selectedPathway}
            onChange={(event) => setSelectedPathway(event.target.value)}
            disabled={!isLoggedIn || locked}
          >
            <option value="">Select a pathway</option>
            {pathways.map((pathway) => (
              <option key={pathway.id} value={pathway.id}>
                {pathway.name}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="mt-6 flex flex-wrap items-center gap-3">
        <button className="cta" onClick={submitSelection} disabled={!isLoggedIn || locked || saving}>
          {saving ? "Saving..." : "Save Selection"}
        </button>
        {message && <span className="text-sm text-[color:var(--muted)]">{message}</span>}
      </div>
    </section>
  );
}
