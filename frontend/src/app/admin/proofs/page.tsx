"use client";

import { useEffect, useState } from "react";
import { apiGet, apiSend } from "@/lib/api";
import { useLocalStorage } from "@/lib/useLocalStorage";
import { useSession } from "@/lib/session";

type Proof = {
  id: string;
  user_id: string;
  checklist_item_id: string;
  proof_type: string;
  url: string;
  view_url?: string | null;
  status: string;
  review_note?: string | null;
};

export default function AdminProofsPage() {
  const { isLoggedIn, username } = useSession();
  const [adminToken, setAdminToken] = useLocalStorage(
    "mp_admin_token",
    "change-me"
  );
  const [proofs, setProofs] = useState<Proof[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [reviewNotes, setReviewNotes] = useState<Record<string, string>>({});

  const headers = { "X-Admin-Token": adminToken };

  const loadProofs = () => {
    const query = statusFilter ? `?status=${statusFilter}` : "";
    apiGet<Proof[]>(`/admin/proofs${query}`, headers)
      .then((data) => {
        setProofs(data);
        const notes: Record<string, string> = {};
        data.forEach((proof) => {
          notes[proof.id] = proof.review_note ?? "";
        });
        setReviewNotes(notes);
      })
      .catch(() => setProofs([]));
  };

  useEffect(() => {
    if (isLoggedIn) {
      loadProofs();
    }
  }, [statusFilter]);

  const updateStatus = async (proofId: string, status: string) => {
    await apiSend(`/admin/proofs/${proofId}`, {
      method: "PUT",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({ status, review_note: reviewNotes[proofId] ?? "" }),
    });
    loadProofs();
  };

  const saveNote = async (proofId: string) => {
    await apiSend(`/admin/proofs/${proofId}`, {
      method: "PUT",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({ review_note: reviewNotes[proofId] ?? "" }),
    });
    loadProofs();
  };

  const deleteProof = async (proofId: string) => {
    await apiSend(`/admin/proofs/${proofId}`, {
      method: "DELETE",
      headers,
    });
    loadProofs();
  };

  return (
    <section className="panel">
      <h2 className="text-2xl font-semibold">Proof Queue</h2>
      <p className="mt-2 text-[color:var(--muted)]">
        {isLoggedIn
          ? `Signed in as ${username}. Review, verify, or reject submitted proof artifacts.`
          : "Log in to review proof submissions safely."}
      </p>
      {!isLoggedIn && (
        <p className="mt-4 text-sm text-[color:var(--accent-2)]">
          Please log in before reviewing proofs.
        </p>
      )}
      <div className="mt-6 grid gap-3">
        <label className="text-sm text-[color:var(--muted)]">
          Admin Token
          <input
            className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
            value={adminToken}
            onChange={(event) => setAdminToken(event.target.value)}
          />
        </label>
      </div>
      <div className="mt-6 flex flex-wrap gap-3">
        <select
          className="rounded-lg border border-[color:var(--border)] p-3"
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value)}
        >
          <option value="">All statuses</option>
          <option value="submitted">Submitted</option>
          <option value="needs_more_evidence">Needs more evidence</option>
          <option value="verified">Verified</option>
          <option value="rejected">Rejected</option>
        </select>
        <button className="cta cta-secondary" onClick={loadProofs}>
          Refresh
        </button>
      </div>
      <div className="mt-6 grid gap-3">
        {proofs.map((row) => (
          <div
            key={row.id}
            className="flex flex-col gap-3 rounded-xl border border-[color:var(--border)] p-4 md:flex-row md:items-center md:justify-between"
          >
            <div>
              <p className="font-medium">{row.proof_type}</p>
              <p className="text-sm text-[color:var(--muted)]">
                {row.user_id} · {row.status}
              </p>
              <a
                className="text-sm text-[color:var(--accent-2)] underline"
                href={row.view_url || row.url}
                target="_blank"
                rel="noreferrer"
              >
                {row.url}
              </a>
            </div>
            <div className="flex flex-1 flex-col gap-3 md:items-end">
              <textarea
                className="w-full max-w-md rounded-lg border border-[color:var(--border)] p-3 text-sm"
                placeholder="Review note for student"
                value={reviewNotes[row.id] ?? ""}
                onChange={(event) =>
                  setReviewNotes((prev) => ({
                    ...prev,
                    [row.id]: event.target.value,
                  }))
                }
              />
              <div className="flex flex-wrap gap-2">
                <button className="cta cta-secondary" onClick={() => saveNote(row.id)}>
                  Save Note
                </button>
                <button className="cta" onClick={() => updateStatus(row.id, "verified")}>
                  Verify
                </button>
                <button
                  className="cta cta-secondary"
                  onClick={() => updateStatus(row.id, "rejected")}
                >
                  Reject
                </button>
                <button
                  className="cta cta-secondary"
                  onClick={() => deleteProof(row.id)}
                >
                  Delete
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
