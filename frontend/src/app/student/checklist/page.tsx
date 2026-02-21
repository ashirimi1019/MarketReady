"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { apiGet, apiSend, API_BASE, getAuthHeaders } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { ChecklistItem, Proof, StorageMeta, Readiness, EvidenceMapResponse } from "@/types/api";

const PROFICIENCY_LEVELS = [
  { value: "beginner", label: "Beginner", desc: "Learning the basics", color: "#ffb300", weight: "50% credit" },
  { value: "intermediate", label: "Intermediate", desc: "Working knowledge", color: "#3d6dff", weight: "75% credit" },
  { value: "professional", label: "Professional", desc: "Production-ready", color: "#00c896", weight: "100% credit" },
] as const;

type ProficiencyValue = "beginner" | "intermediate" | "professional";

function ProficiencySelector({
  value,
  onChange,
  disabled,
  itemId,
}: {
  value: ProficiencyValue;
  onChange: (v: ProficiencyValue) => void;
  disabled: boolean;
  itemId: string;
}) {
  return (
    <div className="space-y-2">
      <p className="text-sm text-[color:var(--muted)]">My proficiency level</p>
      <div className="grid grid-cols-3 gap-2">
        {PROFICIENCY_LEVELS.map(lvl => (
          <button
            key={lvl.value}
            type="button"
            disabled={disabled}
            onClick={() => onChange(lvl.value)}
            data-testid={`proficiency-${lvl.value}-${itemId}`}
            className="relative flex flex-col items-center rounded-xl border p-3 text-center transition-all"
            style={{
              borderColor: value === lvl.value ? lvl.color : "var(--border)",
              background: value === lvl.value ? `${lvl.color}12` : "transparent",
              cursor: disabled ? "not-allowed" : "pointer",
            }}
          >
            <span className="text-sm font-semibold" style={{ color: value === lvl.value ? lvl.color : "var(--muted)" }}>
              {lvl.label}
            </span>
            <span className="text-[10px] mt-0.5" style={{ color: "var(--muted)" }}>{lvl.weight}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function VerificationBadge({ status, reviewNote }: { status: string; reviewNote?: string | null }) {
  if (status === "verified") return (
    <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full font-semibold"
      style={{ background: "rgba(0,200,150,0.12)", color: "#00c896" }}
      data-testid="verification-badge-verified">
      <span>✓</span> AI Verified
    </span>
  );
  if (status === "rejected") return (
    <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full font-semibold"
      style={{ background: "rgba(255,59,48,0.12)", color: "#ff3b30" }}
      title={reviewNote || ""}
      data-testid="verification-badge-rejected">
      ✗ Not Verified
    </span>
  );
  if (status === "submitted" || status === "needs_more_evidence") return (
    <span className="inline-flex items-center gap-2 text-xs px-2 py-1 rounded-full font-semibold"
      style={{ background: "rgba(255,179,0,0.12)", color: "#ffb300" }}
      data-testid="verification-badge-pending">
      <span className="h-2 w-2 rounded-full bg-[#ffb300] animate-pulse" />
      AI Reviewing...
    </span>
  );
  return null;
}

function ProficiencyBadge({ level }: { level: string }) {
  const lvl = PROFICIENCY_LEVELS.find(l => l.value === level) || PROFICIENCY_LEVELS[1];
  return (
    <span className="inline-flex items-center text-[10px] px-1.5 py-0.5 rounded-full font-semibold"
      style={{ background: `${lvl.color}18`, color: lvl.color }}>
      {lvl.label}
    </span>
  );
}

function ChecklistPageContent() {
  const { username, isLoggedIn } = useSession();
  const searchParams = useSearchParams();
  const focusItemId = searchParams.get("item");
  const [items, setItems] = useState<ChecklistItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [proofType, setProofType] = useState<Record<string, string>>({});
  const [proofFile, setProofFile] = useState<Record<string, File | null>>({});
  const [proficiency, setProficiency] = useState<Record<string, ProficiencyValue>>({});
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
    if (proofs.some((proof) => proof.status === "submitted")) return "AI reviewing...";
    if (proofs.some((proof) => proof.status === "needs_more_evidence")) return "needs more evidence";
    if (proofs.some((proof) => proof.status === "rejected")) return "rejected";
    return fallback || "submitted";
  };

  const prettyProofType = (proofTypeValue: string) => {
    if (proofTypeValue === "resume_upload_match") return "resume upload match";
    return proofTypeValue.replace(/_/g, " ");
  };

  const loadProofs = () => {
    if (!isLoggedIn) return;
    apiGet<Proof[]>("/user/proofs", headers)
      .then((proofs) => {
        const grouped: Record<string, Proof[]> = {};
        proofs.forEach((proof) => {
          if (!grouped[proof.checklist_item_id]) grouped[proof.checklist_item_id] = [];
          grouped[proof.checklist_item_id].push(proof);
        });
        setProofsByItem(grouped);
      })
      .catch(() => setProofsByItem({}));
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
    if (target) target.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [focusItemId, items.length]);

  useEffect(() => { loadProofs(); }, [headers, isLoggedIn]);

  useEffect(() => {
    apiGet<StorageMeta>("/meta/storage")
      .then(setStorageMeta)
      .catch(() => setStorageMeta({ s3_enabled: false, local_enabled: true }));
  }, []);

  const submitProof = async (item: ChecklistItem, options: { selfAttested?: boolean } = {}) => {
    if (!isLoggedIn) { setMessage("Please log in first."); return; }
    const allowedProofTypes = item.allowed_proof_types ?? [];
    const selectedType = proofType[item.id] || allowedProofTypes[0];
    const file = proofFile[item.id];
    const requiresDocumentUpload = isCertificateProofType(selectedType || "");
    const selectedProficiency: ProficiencyValue = proficiency[item.id] || "intermediate";

    if (!selectedType) { setMessage("Select a proof type."); return; }
    if (requiresDocumentUpload && !file) { setMessage("Certificate proof requires document upload."); return; }
    if (!requiresDocumentUpload && !options.selfAttested) { setMessage("Use the proficiency button to mark this item."); return; }

    setSaving(item.id);
    setMessage(null);
    try {
      let fileUrl = "";
      if (requiresDocumentUpload && file) {
        const s3Enabled = storageMeta?.s3_enabled ?? false;
        if (s3Enabled) {
          const { upload_url, s3_key } = await apiSend<{ upload_url: string; s3_key: string }>(
            "/user/proofs/presign",
            { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ filename: file.name, content_type: file.type }) }
          );
          await fetch(upload_url, { method: "PUT", body: file });
          fileUrl = s3_key;
        } else {
          const fd = new FormData();
          fd.append("file", file);
          const uploadRes = await fetch(`${API_BASE}/user/proofs/upload`, {
            method: "POST",
            headers: getAuthHeaders(headers),
            body: fd,
          });
          if (!uploadRes.ok) throw new Error("File upload failed");
          const { file_url } = await uploadRes.json();
          fileUrl = file_url;
        }
      }

      const proof = await apiSend<Proof>("/user/proofs", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({
          checklist_item_id: item.id,
          proof_type: selectedType,
          url: requiresDocumentUpload ? fileUrl : "self_attested://yes",
          proficiency_level: selectedProficiency,
          metadata: { filename: file?.name },
        }),
      });

      const isCert = requiresDocumentUpload;
      if (isCert && proof.status === "verified") {
        setMessage(`Certificate AI-verified! Proficiency: ${selectedProficiency}. MRI score updated.`);
      } else if (isCert) {
        setMessage(`Certificate submitted for AI verification. Status: ${proof.status}. Check back soon.`);
      } else {
        setMessage(`Proficiency set to ${selectedProficiency}. MRI score updated.`);
      }

      loadProofs();
      // Re-evaluate readiness
      apiGet<Readiness>("/user/readiness", headers).then(setReevaluation).catch(() => {});
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Submission failed. Please try again.");
    } finally {
      setSaving(null);
    }
  };

  const runEvidenceMapper = async () => {
    if (!isLoggedIn) return;
    setMappingEvidence(true);
    setMappingMessage(null);
    try {
      const result = await apiSend<EvidenceMapResponse>("/ai/evidence-map", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const mapped = result?.mapped_count ?? 0;
      setMappingMessage(mapped > 0 ? `OpenAI Evidence Mapper applied: ${mapped} requirement(s) auto-satisfied from your evidence context.` : "No new requirements could be auto-satisfied. Keep adding evidence.");
      loadProofs();
    } catch (err) {
      setMappingMessage(err instanceof Error ? err.message : "Failed to run OpenAI evidence mapper.");
    } finally {
      setMappingEvidence(false);
    }
  };

  const nonNegotiables = items.filter(i => i.tier === "non_negotiable");
  const strongSignals = items.filter(i => i.tier === "strong_signal");
  const others = items.filter(i => i.tier !== "non_negotiable" && i.tier !== "strong_signal");

  const renderItem = (item: ChecklistItem) => {
    const allowedProofTypes = item.allowed_proof_types ?? [];
    const selectedType = proofType[item.id] ?? allowedProofTypes[0] ?? "";
    const requiresDocumentUpload = isCertificateProofType(selectedType);
    const itemProofs = proofsByItem[item.id] ?? [];
    const displayStatus = getStatusLabel(itemProofs);
    const bestProof = itemProofs.find(p => p.status === "verified") || itemProofs[0];
    const selectedProficiency: ProficiencyValue = proficiency[item.id] || "intermediate";
    const isNonNeg = item.tier === "non_negotiable";

    const statusColors: Record<string, string> = {
      complete: "#00c896",
      "AI reviewing...": "#ffb300",
      "needs more evidence": "#ff7b1a",
      rejected: "#ff3b30",
      "satisfied by resume upload": "#3d6dff",
      incomplete: "var(--muted)",
    };

    return (
      <div
        key={item.id}
        id={`checklist-${item.id}`}
        className="rounded-2xl border p-5 transition-all"
        style={{
          borderColor: focusItemId === item.id ? "var(--primary)" : displayStatus === "complete" ? "rgba(0,200,150,0.2)" : "var(--border)",
          background: displayStatus === "complete" ? "rgba(0,200,150,0.03)" : "transparent",
          boxShadow: focusItemId === item.id ? "0 0 20px rgba(61,109,255,0.2)" : undefined,
        }}
        data-testid={`checklist-item-${item.id}`}
      >
        <div className="flex flex-col md:flex-row md:items-start gap-5">
          {/* Left: item info */}
          <div className="flex-1">
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <span className="text-xs px-2 py-0.5 rounded-full font-semibold"
                style={{ background: `${statusColors[displayStatus] || "var(--muted)"}18`, color: statusColors[displayStatus] || "var(--muted)" }}>
                {displayStatus}
              </span>
              {isNonNeg && (
                <span className="text-[10px] px-2 py-0.5 rounded-full border border-[rgba(255,59,48,0.3)] text-[color:var(--danger)]">
                  Required
                </span>
              )}
              <span className="text-[10px] text-[color:var(--muted)] px-2 py-0.5 rounded-full border border-[color:var(--border)]">
                {(item.tier ?? "core").replace("_", " ")}
              </span>
              {bestProof && <ProficiencyBadge level={bestProof.proficiency_level || "intermediate"} />}
            </div>
            <p className="text-base font-semibold">{item.title}</p>

            {/* Existing proof info */}
            {bestProof && (
              <div className="mt-2 space-y-1">
                <VerificationBadge status={bestProof.status} reviewNote={bestProof.review_note} />
                {bestProof.review_note && bestProof.status !== "verified" && (
                  <p className="text-xs text-[color:var(--muted)]">{bestProof.review_note}</p>
                )}
                {bestProof.url && !bestProof.url.startsWith("self_attested") && (
                  <a
                    className="text-xs text-[color:var(--primary)] underline"
                    href={(bestProof.view_url || bestProof.url).startsWith("http") ? bestProof.view_url || bestProof.url : `${API_BASE}${bestProof.view_url || bestProof.url}`}
                    target="_blank" rel="noreferrer"
                  >
                    View certificate
                  </a>
                )}
              </div>
            )}
          </div>

          {/* Right: submission controls */}
          <div className="flex flex-col gap-3 md:w-72">
            <ProficiencySelector
              value={selectedProficiency}
              onChange={v => setProficiency(prev => ({ ...prev, [item.id]: v }))}
              disabled={!isLoggedIn || saving === item.id}
              itemId={item.id}
            />

            {allowedProofTypes.length > 1 && (
              <select
                className="rounded-lg border border-[color:var(--border)] bg-[color:var(--input-bg)] px-3 py-2 text-sm"
                value={selectedType}
                title={`Proof type for ${item.title}`}
                aria-label={`Proof type for ${item.title}`}
                onChange={e => {
                  setProofType(prev => ({ ...prev, [item.id]: e.target.value }));
                  if (!isCertificateProofType(e.target.value)) setProofFile(prev => ({ ...prev, [item.id]: null }));
                }}
                disabled={!isLoggedIn}
                data-testid={`proof-type-select-${item.id}`}
              >
                {allowedProofTypes.map(type => (
                  <option key={type} value={type}>{prettyProofType(type)}</option>
                ))}
              </select>
            )}

            {requiresDocumentUpload ? (
              <div className="space-y-2">
                {isNonNeg && (
                  <div className="text-xs rounded-lg p-2 border border-[rgba(61,109,255,0.2)] bg-[rgba(61,109,255,0.05)]">
                    <span className="font-semibold text-[color:var(--primary)]">Required: </span>
                    <span className="text-[color:var(--muted)]">AI will verify this certificate automatically</span>
                  </div>
                )}
                <label className="text-xs text-[color:var(--muted)]">
                  Upload certificate
                  <input
                    id={`certificate-upload-${item.id}`}
                    type="file"
                    accept=".pdf,.jpg,.jpeg,.png,.webp"
                    className="mt-1 w-full rounded-lg border border-[color:var(--border)] p-2 text-sm"
                    title={`Upload certificate for ${item.title}`}
                    aria-label={`Upload certificate for ${item.title}`}
                    onChange={e => setProofFile(prev => ({ ...prev, [item.id]: e.target.files?.[0] ?? null }))}
                    disabled={!isLoggedIn}
                    data-testid={`cert-upload-${item.id}`}
                  />
                </label>
                <button
                  className="cta cta-primary w-full text-sm"
                  onClick={() => submitProof(item)}
                  disabled={!isLoggedIn || saving === item.id}
                  data-testid={`submit-cert-btn-${item.id}`}
                >
                  {saving === item.id ? (
                    <span className="flex items-center justify-center gap-2">
                      <span className="h-3 w-3 rounded-full border border-white border-t-transparent animate-spin" />
                      AI Verifying...
                    </span>
                  ) : "Submit & AI Verify"}
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-2">
                <button
                  className="cta cta-primary text-sm"
                  onClick={() => submitProof(item, { selfAttested: true })}
                  disabled={!isLoggedIn || saving === item.id}
                  data-testid={`mark-proficient-btn-${item.id}`}
                >
                  {saving === item.id ? "Saving..." : `Mark as ${PROFICIENCY_LEVELS.find(l => l.value === selectedProficiency)?.label}`}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  const sectionGroups = [
    { label: "Required (Non-Negotiable)", items: nonNegotiables, color: "#ff3b30" },
    { label: "Strong Signals", items: strongSignals, color: "#ffb300" },
    { label: "Core Skills", items: others, color: "var(--muted)" },
  ].filter(g => g.items.length > 0);

  return (
    <section className="panel space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Skills Checklist</h2>
        <p className="mt-1 text-[color:var(--muted)] text-sm">
          Set your proficiency level for each skill. Non-negotiable certificates are AI-verified for authenticity.
        </p>
      </div>

      {/* Proficiency legend */}
      <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)] p-4">
        <p className="text-xs font-semibold text-[color:var(--muted)] mb-3 uppercase tracking-wider">How Proficiency Affects Your MRI Score</p>
        <div className="grid grid-cols-3 gap-3">
          {PROFICIENCY_LEVELS.map(lvl => (
            <div key={lvl.value} className="text-center p-2 rounded-xl border border-[color:var(--border)]">
              <p className="font-semibold text-sm" style={{ color: lvl.color }}>{lvl.label}</p>
              <p className="text-xs text-[color:var(--muted)] mt-0.5">{lvl.weight}</p>
              <p className="text-[10px] text-[color:var(--muted)] mt-0.5">{lvl.desc}</p>
            </div>
          ))}
        </div>
        <p className="text-xs text-[color:var(--muted)] mt-3">
          AI-verified certificates on Required items get an additional <span className="text-[color:var(--success)] font-semibold">15% bonus</span>.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button className="cta cta-secondary text-sm" onClick={runEvidenceMapper} disabled={!isLoggedIn || mappingEvidence} data-testid="evidence-mapper-btn">
          {mappingEvidence ? "Mapping Evidence..." : "Run OpenAI Evidence Mapper"}
        </button>
        {mappingMessage && <span className="text-sm text-[color:var(--muted)]">{mappingMessage}</span>}
      </div>

      {!isLoggedIn && <p className="text-sm text-[color:var(--accent-2)]">Please log in to view your checklist.</p>}
      {message && <p className="text-sm text-[color:var(--success)] rounded-xl border border-[rgba(0,200,150,0.2)] bg-[rgba(0,200,150,0.06)] px-4 py-2" data-testid="checklist-message">{message}</p>}
      {error && <p className="text-sm text-[color:var(--danger)]">{error}</p>}

      {reevaluation && (
        <div className="rounded-xl border border-[color:var(--border)] bg-[color:var(--surface)] p-4 text-sm">
          <div className="font-semibold">MRI recalculated: {reevaluation.score.toFixed(0)}/100 ({reevaluation.band})</div>
          {reevaluation.next_actions?.length ? (
            <div className="mt-1 text-[color:var(--muted)]">Next: {reevaluation.next_actions.slice(0, 2).join(" • ")}</div>
          ) : null}
        </div>
      )}

      {sectionGroups.map(group => (
        <div key={group.label} className="space-y-3">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full" style={{ background: group.color }} />
            <h3 className="text-sm font-semibold uppercase tracking-wider text-[color:var(--muted)]">{group.label}</h3>
            <span className="text-xs text-[color:var(--muted)]">({group.items.length})</span>
          </div>
          {group.items.map(renderItem)}
        </div>
      ))}
    </section>
  );
}

export default function StudentChecklistPage() {
  return (
    <Suspense fallback={
      <section className="panel">
        <h2 className="text-3xl font-bold">Skills Checklist</h2>
        <p className="mt-2 text-[color:var(--muted)]">Loading...</p>
      </section>
    }>
      <ChecklistPageContent />
    </Suspense>
  );
}
