"use client";

import { useEffect, useMemo, useState } from "react";
import { apiGet, API_BASE } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { Proof, ChecklistItem } from "@/types/api";

export default function StudentProofsPage() {
  const { username, isLoggedIn } = useSession();
  const headers = useMemo(() => ({ "X-User-Id": username }), [username]);
  const [proofs, setProofs] = useState<Proof[]>([]);
  const [itemMap, setItemMap] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoggedIn) return;
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
  }, [headers, isLoggedIn]);

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
        Track verification status and review notes from admins.
      </p>
      {!isLoggedIn && (
        <p className="mt-4 text-sm text-[color:var(--accent-2)]">
          Please log in to view your proofs.
        </p>
      )}
      {error && (
        <p className="mt-4 text-sm text-[color:var(--accent-2)]">{error}</p>
      )}
      <div className="mt-6 grid gap-3">
        {proofs.length === 0 && isLoggedIn && (
          <div className="text-sm text-[color:var(--muted)]">
            No proofs submitted yet.
          </div>
        )}
        {proofs.map((proof) => (
          <div
            key={proof.id}
            className="rounded-xl border border-[color:var(--border)] p-5"
          >
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
              {proof.review_note && (
                <p className="mt-2 text-sm text-[color:var(--muted)]">
                  Admin note: {proof.review_note}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
