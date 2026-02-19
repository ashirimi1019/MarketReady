"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { apiGet, apiSend, API_BASE, getAuthHeaders } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { ChecklistItem, Proof, StorageMeta, Readiness, EvidenceMapResponse } from "@/types/api";

function ChecklistPageContent() {
  const { username, isLoggedIn } = useSession();
  const searchParams = useSearchParams();
  const focusItemId = searchParams.get("item");
  const [items, setItems] = useState<ChecklistItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [proofType, setProofType] = useState<Record<string, string>>({});
  const [proofFile, setProofFile] = useState<Record<string, File | null>>({});
  const [proofsByItem, setProofsByItem] = useState<Record<string, Proof[]>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [storageMeta, setStorageMeta] = useState<StorageMeta | null>(null);
  const [reevaluation, setReevaluation] = useState<Readiness | null>(null);
  const [mappingEvidence, setMappingEvidence] = useState(false);
  const [mappingMessage, setMappingMessage] = useState<string | null>(null);

  const headers = useMemo(() => ({ "X-User-Id": username }), [username]);

  const isCertificateProofType = (value: string) => {
    const normalized = value.trim().toLowerCase();
    return normalized === "cert_upload" || normalized.includes("cert");
  };

  const getStatusLabel = (proofs: Proof[], fallback?: string) => {
    if (!proofs.length) return "incomplete";
    const verifiedProofs = proofs.filter((proof) => proof.status === "verified");
    if (verifiedProofs.length) {
      const hasOnlyResumeMatches = verifiedProofs.every(
        (proof) => proof.proof_type === "resume_upload_match"
      );
      return hasOnlyResumeMatches ? "satisfied by resume upload" : "complete";
    }
    if (proofs.some((proof) => proof.status === "submitted")) {
      return "waiting for verification";
    }
    if (proofs.some((proof) => proof.status === "needs_more_evidence")) {
      return "needs more evidence";
    }
    if (proofs.some((proof) => proof.status === "rejected")) return "rejected";
    return fallback || "submitted";
  };

  const prettyProofType = (proofTypeValue: string) => {
    if (proofTypeValue === "resume_upload_match") return "resume upload match";
    return proofTypeValue.replace(/_/g, " ");
  };

  useEffect(() => {
    if (!isLoggedIn) return;
    apiGet<ChecklistItem[]>("/user/checklist", headers)
      .then(setItems)
      .catch(() => setError("Unable to load checklist."));
  }, [headers, isLoggedIn]);

  useEffect(() => {
    if (!focusItemId) return;
    const target = document.getElementById(`checklist-${focusItemId}`);
    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [focusItemId, items.length]);

  useEffect(() => {
    if (!isLoggedIn) return;
    apiGet<Proof[]>("/user/proofs", headers)
      .then((proofs) => {
        const grouped: Record<string, Proof[]> = {};
        proofs.forEach((proof) => {
          if (!grouped[proof.checklist_item_id]) {
            grouped[proof.checklist_item_id] = [];
          }
          grouped[proof.checklist_item_id].push(proof);
        });
        setProofsByItem(grouped);
      })
      .catch(() => setProofsByItem({}));
  }, [headers, isLoggedIn]);

  useEffect(() => {
    apiGet<StorageMeta>("/meta/storage")
      .then(setStorageMeta)
      .catch(() =>
        setStorageMeta({
          s3_enabled: false,
          local_enabled: true,
        })
      );
  }, []);

  const submitProof = async (
    item: ChecklistItem,
    options: { selfAttested?: boolean } = {}
  ) => {
    if (!isLoggedIn) {
      setMessage("Please log in first.");
      return;
    }
    const allowedProofTypes = item.allowed_proof_types ?? [];
    const selectedType = proofType[item.id] || allowedProofTypes[0];
    const file = proofFile[item.id];
    const requiresDocumentUpload = isCertificateProofType(selectedType || "");
    if (!selectedType) {
      setMessage("Select a proof type.");
      return;
    }
    if (requiresDocumentUpload && !file) {
      setMessage("Certificate proof requires document upload.");
      return;
    }
    if (!requiresDocumentUpload && !options.selfAttested) {
      setMessage("For non-certificate items, use the Yes self-attestation button.");
      return;
    }
    setSaving(item.id);
    setMessage(null);
    try {
      let proofLocation = requiresDocumentUpload ? "" : "self_attested://yes";
      let storageKey: string | null = null;
      if (requiresDocumentUpload && file) {
        const fileContentType = file.type || "application/octet-stream";
        const useS3 = storageMeta?.s3_enabled;
        if (useS3) {
          try {
            const presign = await apiSend<{
              upload_url: string;
              file_url: string;
              key: string;
            }>("/user/proofs/presign", {
              method: "POST",
              headers: {
                ...headers,
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                filename: file.name,
                content_type: fileContentType,
              }),
            });

            const upload = await fetch(presign.upload_url, {
              method: "PUT",
              headers: {
                "Content-Type": fileContentType,
              },
              body: file,
            });
            if (!upload.ok) {
              throw new Error("S3 upload failed.");
            }
            proofLocation = presign.file_url;
            storageKey = presign.key ?? null;
          } catch (err) {
            if (!storageMeta?.local_enabled) {
              throw err;
            }
            const form = new FormData();
            form.append("file", file);
            const upload = await fetch(`${API_BASE}/user/proofs/upload`, {
              method: "POST",
              headers: getAuthHeaders(headers),
              body: form,
            });
            if (!upload.ok) {
              throw new Error("Local upload failed.");
            }
            const uploaded = await upload.json();
            proofLocation = uploaded.file_url;
          }
        } else {
          const form = new FormData();
          form.append("file", file);
          const upload = await fetch(`${API_BASE}/user/proofs/upload`, {
            method: "POST",
            headers: getAuthHeaders(headers),
            body: form,
          });
          if (!upload.ok) {
            throw new Error("Local upload failed.");
          }
          const uploaded = await upload.json();
          proofLocation = uploaded.file_url;
        }
      }

      if (!proofLocation) {
        throw new Error("Could not determine proof file location.");
      }

      const created = await apiSend<Proof>("/user/proofs", {
        method: "POST",
        headers: {
          ...headers,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          checklist_item_id: item.id,
          proof_type: selectedType,
          url: proofLocation,
          metadata: {
            ...(requiresDocumentUpload && file
              ? {
                  filename: file.name,
                  size: file.size,
                  content_type: file.type,
                  storage_key: storageKey,
                }
              : {}),
            ...(requiresDocumentUpload
              ? {}
              : {
                  self_attested: true,
                  attestation: "yes",
                }),
          },
        }),
      });
      const proofs = await apiGet<Proof[]>("/user/proofs", headers);
      const grouped: Record<string, Proof[]> = {};
      proofs.forEach((proof) => {
        if (!grouped[proof.checklist_item_id]) {
          grouped[proof.checklist_item_id] = [];
        }
        grouped[proof.checklist_item_id].push(proof);
      });
      setProofsByItem(grouped);
      const updated = await apiGet<ChecklistItem[]>("/user/checklist", headers);
      setItems(updated);
      const readiness = await apiGet<Readiness>("/user/readiness", headers).catch(
        () => null
      );
      setReevaluation(readiness);
      if (!requiresDocumentUpload && created.status === "verified") {
        setMessage("Marked complete by self-attestation. Readiness updated.");
      } else if (created.status === "verified") {
        setMessage("Submission verified by OpenAI and profile needs were re-evaluated.");
      } else if (created.status === "needs_more_evidence") {
        setMessage("Submission recorded. OpenAI needs more evidence for verification.");
      } else if (created.status === "rejected") {
        setMessage("Submission recorded, but OpenAI rejected it for this requirement.");
      } else {
        setMessage("Submission recorded and readiness re-evaluated.");
      }
      setProofFile((prev) => ({ ...prev, [item.id]: null }));
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to submit proof.");
    } finally {
      setSaving(null);
    }
  };

  const runEvidenceMapper = async () => {
    if (!isLoggedIn) {
      setMappingMessage("Please log in first.");
      return;
    }
    setMappingEvidence(true);
    setMappingMessage(null);
    try {
      const result = await apiSend<EvidenceMapResponse>("/user/ai/evidence-map", {
        method: "POST",
        headers,
      });
      const [updatedItems, updatedProofs, readiness] = await Promise.all([
        apiGet<ChecklistItem[]>("/user/checklist", headers).catch(() => null),
        apiGet<Proof[]>("/user/proofs", headers).catch(() => null),
        apiGet<Readiness>("/user/readiness", headers).catch(() => null),
      ]);
      if (updatedItems) {
        setItems(updatedItems);
      }
      if (updatedProofs) {
        const grouped: Record<string, Proof[]> = {};
        updatedProofs.forEach((proof) => {
          if (!grouped[proof.checklist_item_id]) {
            grouped[proof.checklist_item_id] = [];
          }
          grouped[proof.checklist_item_id].push(proof);
        });
        setProofsByItem(grouped);
      }
      setReevaluation(readiness);
      if (result.matched_count > 0) {
        setMappingMessage(
          `OpenAI mapped ${result.matched_count} requirement(s) from uploaded evidence.`
        );
      } else {
        setMappingMessage(
          "No additional requirements were mapped from current evidence."
        );
      }
    } catch (err) {
      setMappingMessage(
        err instanceof Error ? err.message : "Failed to run OpenAI evidence mapper."
      );
    } finally {
      setMappingEvidence(false);
    }
  };

  return (
    <section className="panel">
      <h2 className="text-3xl font-semibold">Checklist</h2>
      <p className="mt-2 text-[color:var(--muted)]">
        Mark non-certificate items as done with Yes/No attestation. Certificates require upload + OpenAI verification.
      </p>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          className="cta cta-secondary text-base"
          onClick={runEvidenceMapper}
          disabled={!isLoggedIn || mappingEvidence}
        >
          {mappingEvidence ? "Mapping Evidence..." : "Run OpenAI Evidence Mapper"}
        </button>
        {mappingMessage && (
          <span className="text-sm text-[color:var(--muted)]">
            {mappingMessage}
          </span>
        )}
      </div>
      {!isLoggedIn && (
        <p className="mt-4 text-sm text-[color:var(--accent-2)]">
          Please log in to view your checklist.
        </p>
      )}
      {message && (
        <p className="mt-4 text-sm text-[color:var(--accent-2)]">{message}</p>
      )}
      {error && (
        <p className="mt-4 text-sm text-[color:var(--accent-2)]">{error}</p>
      )}
      {reevaluation && (
        <div className="mt-4 rounded-xl border border-[color:var(--border)] p-4 text-sm text-[color:var(--muted)]">
          <div className="font-medium text-white">
            Profile re-evaluated: readiness {reevaluation.score.toFixed(0)}/100 (
            {reevaluation.band})
          </div>
          <div className="mt-1">
            Further needs:{" "}
            {reevaluation.next_actions?.length
              ? reevaluation.next_actions.slice(0, 3).join(" • ")
              : "No immediate actions."}
          </div>
        </div>
      )}
      <div className="mt-8 grid gap-4">
        {items.map((item) => {
          const allowedProofTypes = item.allowed_proof_types ?? [];
          const selectedType = proofType[item.id] ?? allowedProofTypes[0] ?? "";
          const requiresDocumentUpload = isCertificateProofType(selectedType);
          return (
            <div
              key={item.id}
              id={`checklist-${item.id}`}
              className={`flex flex-col gap-3 rounded-2xl border p-6 md:flex-row md:items-center md:justify-between ${
                focusItemId === item.id
                  ? "border-[color:var(--accent-2)] shadow-[0_0_20px_rgba(61,214,208,0.3)]"
                  : "border-[color:var(--border)]"
              }`}
            >
            <div>
              {(() => {
                const proofs = proofsByItem[item.id] ?? [];
                const displayStatus = getStatusLabel(proofs, item.status);
                return (
                  <span className="chip mb-2 inline-flex">
                    {displayStatus}
                  </span>
                );
              })()}
              <p className="text-lg font-semibold">{item.title}</p>
              <span className="text-sm text-[color:var(--muted)]">
                {(item.tier ?? "core").replace("_", " ")}
              </span>
              {proofsByItem[item.id]?.[0] && (
                <div className="mt-3 text-sm text-[color:var(--muted)]">
                  <div>
                    Saved proof ({prettyProofType(proofsByItem[item.id][0].proof_type)},{" "}
                    {proofsByItem[item.id][0].status})
                  </div>
                  {proofsByItem[item.id][0].review_note && (
                    <div className="mt-1 text-[color:var(--accent-2)]">
                      Admin note: {proofsByItem[item.id][0].review_note}
                    </div>
                  )}
                  <a
                    className="text-[color:var(--accent-2)] underline"
                    href={
                      (proofsByItem[item.id][0].view_url ||
                        proofsByItem[item.id][0].url).startsWith("http")
                        ? proofsByItem[item.id][0].view_url ||
                          proofsByItem[item.id][0].url
                        : `${API_BASE}${proofsByItem[item.id][0].view_url || proofsByItem[item.id][0].url}`
                    }
                    target="_blank"
                    rel="noreferrer"
                  >
                    {proofsByItem[item.id][0].url}
                  </a>
                </div>
              )}
            </div>
            <div className="flex flex-1 flex-col gap-3 md:max-w-md">
              <label
                htmlFor={`proof-type-${item.id}`}
                className="text-sm text-[color:var(--muted)]"
              >
                Proof type
              </label>
              <select
                id={`proof-type-${item.id}`}
                className="rounded-lg border border-[color:var(--border)] p-3 text-base"
                value={selectedType}
                title={`Proof type for ${item.title}`}
                aria-label={`Proof type for ${item.title}`}
                onChange={(event) => {
                  const nextType = event.target.value;
                  setProofType((prev) => ({ ...prev, [item.id]: nextType }));
                  if (!isCertificateProofType(nextType)) {
                    setProofFile((prev) => ({ ...prev, [item.id]: null }));
                  }
                }}
                disabled={!isLoggedIn}
              >
                {(allowedProofTypes.length
                  ? allowedProofTypes
                  : ["repo_url"]).map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
              {requiresDocumentUpload ? (
                <>
                  <div className="rounded-lg border border-dashed border-[color:var(--border)] p-3 text-sm text-[color:var(--muted)]">
                    Certificate proofs require file upload and OpenAI authenticity verification.
                  </div>
                  <label
                    htmlFor={`certificate-upload-${item.id}`}
                    className="text-sm text-[color:var(--muted)]"
                  >
                    Upload certificate document
                  </label>
                  <input
                    id={`certificate-upload-${item.id}`}
                    type="file"
                    className="rounded-lg border border-[color:var(--border)] p-3 text-base"
                    title={`Upload certificate file for ${item.title}`}
                    aria-label={`Upload certificate file for ${item.title}`}
                    onChange={(event) =>
                      setProofFile((prev) => ({
                        ...prev,
                        [item.id]: event.target.files?.[0] ?? null,
                      }))
                    }
                    disabled={!isLoggedIn}
                  />
                  <button
                    className="cta cta-secondary text-base"
                    onClick={() => submitProof(item)}
                    disabled={!isLoggedIn || saving === item.id}
                  >
                    {saving === item.id ? "Submitting..." : "Submit Certificate"}
                  </button>
                </>
              ) : (
                <>
                  <div className="rounded-lg border border-dashed border-[color:var(--border)] p-3 text-sm text-[color:var(--muted)]">
                    Non-certificate items are self-attested. Click Yes if you have completed this requirement.
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      className="cta cta-secondary text-base"
                      onClick={() => submitProof(item, { selfAttested: true })}
                      disabled={!isLoggedIn || saving === item.id}
                    >
                      {saving === item.id ? "Saving..." : "Yes, I completed this"}
                    </button>
                    <button
                      className="cta cta-secondary text-base"
                      onClick={() =>
                        setMessage("No problem. Keep this item open and complete it later.")
                      }
                      disabled={!isLoggedIn || saving === item.id}
                    >
                      No, not yet
                    </button>
                  </div>
                </>
              )}
            </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export default function StudentChecklistPage() {
  return (
    <Suspense
      fallback={
        <section className="panel">
          <h2 className="text-3xl font-semibold">Checklist</h2>
          <p className="mt-2 text-[color:var(--muted)]">Loading checklist...</p>
        </section>
      }
    >
      <ChecklistPageContent />
    </Suspense>
  );
}
