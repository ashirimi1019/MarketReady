"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet, apiSend } from "@/lib/api";
import { useLocalStorage } from "@/lib/useLocalStorage";
import { useSession } from "@/lib/session";

type MarketSignal = {
  id: string;
  pathway_id?: string | null;
  skill_id?: string | null;
  skill_name?: string | null;
  role_family?: string | null;
  window_start?: string | null;
  window_end?: string | null;
  frequency?: number | null;
  source_count?: number | null;
  metadata?: Record<string, unknown> | null;
};

type MarketProposal = {
  id: string;
  pathway_id: string;
  proposed_version_number?: number | null;
  status: string;
  summary?: string | null;
  diff?: Record<string, unknown> | null;
  created_at: string;
  approved_at?: string | null;
};

export default function AdminMarketPage() {
  const { isLoggedIn, username } = useSession();
  const [adminToken, setAdminToken] = useLocalStorage(
    "mp_admin_token",
    "change-me"
  );
  const [pathwayId, setPathwayId] = useState("");
  const [skillName, setSkillName] = useState("");
  const [roleFamily, setRoleFamily] = useState("");
  const [frequency, setFrequency] = useState("");
  const [sourceCount, setSourceCount] = useState("");
  const [windowStart, setWindowStart] = useState("");
  const [windowEnd, setWindowEnd] = useState("");
  const [metadataJson, setMetadataJson] = useState("");
  const [externalProvider, setExternalProvider] = useState("adzuna");
  const [externalQuery, setExternalQuery] = useState("software engineer");
  const [externalLimit, setExternalLimit] = useState("25");

  const [proposalPathwayId, setProposalPathwayId] = useState("");
  const [proposalSummary, setProposalSummary] = useState("");
  const [proposalDiff, setProposalDiff] = useState("");
  const [proposalMessage, setProposalMessage] = useState<string | null>(null);
  const [proposalSaving, setProposalSaving] = useState(false);
  const [copilotInstruction, setCopilotInstruction] = useState("");

  const [lastSignal, setLastSignal] = useState<Record<string, unknown> | null>(
    null
  );
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [signals, setSignals] = useState<MarketSignal[]>([]);
  const [selectedSignals, setSelectedSignals] = useState<Record<string, boolean>>(
    {}
  );
  const [signalsError, setSignalsError] = useState<string | null>(null);

  const [proposals, setProposals] = useState<MarketProposal[]>([]);
  const [proposalsError, setProposalsError] = useState<string | null>(null);
  const [approvingProposalId, setApprovingProposalId] = useState<string | null>(
    null
  );
  const [publishingProposalId, setPublishingProposalId] = useState<string | null>(
    null
  );

  const headers = useMemo(() => ({ "X-Admin-Token": adminToken }), [adminToken]);

  const loadSignals = useCallback(() => {
    setSignalsError(null);
    apiGet<MarketSignal[]>("/admin/market/signals", headers)
      .then((data) => {
        setSignals(data);
        const selected: Record<string, boolean> = {};
        data.forEach((signal) => {
          selected[signal.id] = false;
        });
        setSelectedSignals(selected);
      })
      .catch(() => setSignalsError("Unable to load market signals."));
  }, [headers]);

  const loadProposals = useCallback(() => {
    setProposalsError(null);
    apiGet<MarketProposal[]>("/admin/market/proposals", headers)
      .then(setProposals)
      .catch(() => setProposalsError("Unable to load proposals."));
  }, [headers]);

  useEffect(() => {
    if (!isLoggedIn) return;
    loadSignals();
    loadProposals();
  }, [isLoggedIn, loadSignals, loadProposals]);

  const toggleSignal = (id: string) => {
    setSelectedSignals((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const selectAllSignals = () => {
    const all: Record<string, boolean> = {};
    signals.forEach((signal) => {
      all[signal.id] = true;
    });
    setSelectedSignals(all);
  };

  const clearAllSignals = () => {
    const cleared: Record<string, boolean> = {};
    signals.forEach((signal) => {
      cleared[signal.id] = false;
    });
    setSelectedSignals(cleared);
  };

  const submitSignal = async () => {
    setMessage(null);
    if (!isLoggedIn) {
      setMessage("Please log in before submitting signals.");
      return;
    }
    let metadata: Record<string, unknown> | null = null;
    if (metadataJson.trim()) {
      try {
        metadata = JSON.parse(metadataJson);
      } catch {
        setMessage("Metadata must be valid JSON.");
        return;
      }
    }
    const payload = {
      signals: [
        {
          pathway_id: pathwayId || null,
          skill_name: skillName || null,
          role_family: roleFamily || null,
          window_start: windowStart ? new Date(windowStart).toISOString() : null,
          window_end: windowEnd ? new Date(windowEnd).toISOString() : null,
          frequency: frequency ? Number(frequency) : null,
          source_count: sourceCount ? Number(sourceCount) : null,
          metadata,
        },
      ],
    };
    setSaving(true);
    try {
      await apiSend("/admin/market/signals", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setMessage("Market signal recorded.");
      setLastSignal(payload.signals[0]);
      loadSignals();
      setPathwayId("");
      setSkillName("");
      setRoleFamily("");
      setFrequency("");
      setSourceCount("");
      setWindowStart("");
      setWindowEnd("");
      setMetadataJson("");
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Failed to record signal."
      );
    } finally {
      setSaving(false);
    }
  };

  const runExternalIngest = async () => {
    if (!isLoggedIn) {
      setMessage("Please log in before ingesting external data.");
      return;
    }
    setMessage(null);
    setSaving(true);
    try {
      const result = await apiSend<{ provider: string; ingested: number; created_signals: number }>(
        "/admin/market/ingest/external",
        {
          method: "POST",
          headers: { ...headers, "Content-Type": "application/json" },
          body: JSON.stringify({
            provider: externalProvider,
            pathway_id: pathwayId || null,
            query: externalQuery || null,
            role_family: roleFamily || null,
            limit: Number(externalLimit || "25"),
          }),
        }
      );
      setMessage(
        `External ingest complete (${result.provider}): ${result.ingested} rows, ${result.created_signals} signals.`
      );
      loadSignals();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "External ingest failed.");
    } finally {
      setSaving(false);
    }
  };

  const createProposal = async () => {
    setProposalMessage(null);
    if (!isLoggedIn) {
      setProposalMessage("Please log in before creating proposals.");
      return;
    }
    if (!proposalPathwayId.trim()) {
      setProposalMessage("Pathway ID is required.");
      return;
    }
    let diff: Record<string, unknown> | null = null;
    if (proposalDiff.trim()) {
      try {
        diff = JSON.parse(proposalDiff);
      } catch {
        setProposalMessage("Proposal diff must be valid JSON.");
        return;
      }
    }
    setProposalSaving(true);
    try {
      await apiSend("/admin/market/proposals", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({
          pathway_id: proposalPathwayId,
          summary: proposalSummary || null,
          diff,
        }),
      });
      setProposalMessage("Draft proposal created.");
      setProposalSummary("");
      setProposalDiff("");
      loadProposals();
    } catch (error) {
      setProposalMessage(
        error instanceof Error ? error.message : "Failed to create proposal."
      );
    } finally {
      setProposalSaving(false);
    }
  };

  const useLastSignal = () => {
    if (!lastSignal) {
      setProposalMessage("Submit a market signal first.");
      return;
    }
    const signal = lastSignal as Record<string, unknown>;
    const pathway = signal.pathway_id as string | undefined;
    const skill = signal.skill_name as string | undefined;
    if (pathway) {
      setProposalPathwayId(String(pathway));
    }
    setProposalSummary(
      `Draft update based on market signal for ${skill || "skill"}`
    );
    setProposalDiff(JSON.stringify({ signal }, null, 2));
  };

  const createProposalFromSelected = async () => {
    setProposalMessage(null);
    if (!isLoggedIn) {
      setProposalMessage("Please log in before creating proposals.");
      return;
    }
    const selected = signals.filter((signal) => selectedSignals[signal.id]);
    if (selected.length === 0) {
      setProposalMessage("Select at least one signal.");
      return;
    }

    let pathway = proposalPathwayId.trim();
    if (!pathway) {
      const pathways = Array.from(
        new Set(selected.map((signal) => signal.pathway_id).filter(Boolean))
      );
      if (pathways.length === 1) {
        pathway = String(pathways[0]);
        setProposalPathwayId(pathway);
      }
    }
    if (!pathway) {
      setProposalMessage("Pathway ID is required for proposals.");
      return;
    }

    setProposalSaving(true);
    try {
      const created = await apiSend<MarketProposal>(
        "/admin/market/proposals/copilot",
        {
          method: "POST",
          headers: { ...headers, "Content-Type": "application/json" },
          body: JSON.stringify({
            pathway_id: pathway,
            signal_ids: selected.map((signal) => signal.id),
            instruction: copilotInstruction || null,
          }),
        }
      );
      setProposalMessage(
        `Copilot draft proposal created from ${selected.length} selected signals.`
      );
      setProposalSummary(created.summary ?? "");
      setProposalDiff(JSON.stringify(created.diff ?? { signals: selected }, null, 2));
      loadProposals();
    } catch (error) {
      setProposalMessage(
        error instanceof Error ? error.message : "Failed to create proposal."
      );
    } finally {
      setProposalSaving(false);
    }
  };

  const approveProposal = async (proposalId: string) => {
    setProposalsError(null);
    setApprovingProposalId(proposalId);
    try {
      await apiSend<MarketProposal>(`/admin/market/proposals/${proposalId}/approve`, {
        method: "POST",
        headers,
      });
      loadProposals();
    } catch (error) {
      setProposalsError(
        error instanceof Error ? error.message : "Failed to approve proposal."
      );
    } finally {
      setApprovingProposalId(null);
    }
  };

  const publishProposal = async (proposalId: string) => {
    setProposalsError(null);
    setPublishingProposalId(proposalId);
    try {
      await apiSend<MarketProposal>(`/admin/market/proposals/${proposalId}/publish`, {
        method: "POST",
        headers,
      });
      loadProposals();
    } catch (error) {
      setProposalsError(
        error instanceof Error ? error.message : "Failed to publish proposal."
      );
    } finally {
      setPublishingProposalId(null);
    }
  };

  return (
    <section className="panel">
      <h2 className="text-2xl font-semibold">Market Signals (Manual)</h2>
      <p className="mt-2 text-[color:var(--muted)]">
        {isLoggedIn
          ? `Signed in as ${username}. Log market signals manually to test the pipeline.`
          : "Log in to submit market signals."}
      </p>
      {!isLoggedIn && (
        <p className="mt-4 text-sm text-[color:var(--accent-2)]">
          Please log in before submitting signals.
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

      <div className="mt-6 grid gap-4 md:grid-cols-2">
        <label className="text-sm text-[color:var(--muted)]">
          Pathway ID (optional)
          <input
            className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
            value={pathwayId}
            onChange={(event) => setPathwayId(event.target.value)}
          />
        </label>
        <label className="text-sm text-[color:var(--muted)]">
          Skill Name (optional)
          <input
            className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
            value={skillName}
            onChange={(event) => setSkillName(event.target.value)}
          />
        </label>
        <label className="text-sm text-[color:var(--muted)]">
          Role Family
          <input
            className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
            value={roleFamily}
            onChange={(event) => setRoleFamily(event.target.value)}
          />
        </label>
        <label className="text-sm text-[color:var(--muted)]">
          Frequency
          <input
            className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
            value={frequency}
            onChange={(event) => setFrequency(event.target.value)}
            placeholder="e.g., 0.42"
          />
        </label>
        <label className="text-sm text-[color:var(--muted)]">
          Source Count
          <input
            className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
            value={sourceCount}
            onChange={(event) => setSourceCount(event.target.value)}
            placeholder="e.g., 15"
          />
        </label>
        <label className="text-sm text-[color:var(--muted)]">
          Window Start
          <input
            type="date"
            className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
            value={windowStart}
            onChange={(event) => setWindowStart(event.target.value)}
          />
        </label>
        <label className="text-sm text-[color:var(--muted)]">
          Window End
          <input
            type="date"
            className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
            value={windowEnd}
            onChange={(event) => setWindowEnd(event.target.value)}
          />
        </label>
      </div>

      <div className="mt-6">
        <label className="text-sm text-[color:var(--muted)]">
          Metadata (JSON, optional)
          <textarea
            className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3 text-sm"
            value={metadataJson}
            onChange={(event) => setMetadataJson(event.target.value)}
            placeholder='{"source":"manual","notes":"testing"}'
          />
        </label>
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <button className="cta" onClick={submitSignal} disabled={!isLoggedIn || saving}>
          {saving ? "Submitting..." : "Submit Signal"}
        </button>
        <button className="cta cta-secondary" onClick={runExternalIngest} disabled={!isLoggedIn || saving}>
          {saving ? "Running..." : "Ingest External Data"}
        </button>
        {message && <span className="text-sm text-[color:var(--muted)]">{message}</span>}
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <label className="text-sm text-[color:var(--muted)]">
          External Provider
          <select
            className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
            value={externalProvider}
            onChange={(event) => setExternalProvider(event.target.value)}
          >
            <option value="adzuna">Adzuna</option>
            <option value="onet">O*NET</option>
            <option value="careeronestop">CareerOneStop</option>
          </select>
        </label>
        <label className="text-sm text-[color:var(--muted)]">
          External Query
          <input
            className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
            value={externalQuery}
            onChange={(event) => setExternalQuery(event.target.value)}
          />
        </label>
        <label className="text-sm text-[color:var(--muted)]">
          Limit
          <input
            className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
            value={externalLimit}
            onChange={(event) => setExternalLimit(event.target.value)}
          />
        </label>
      </div>

      <div className="divider" />

      <h3 className="text-xl font-semibold">Manual Draft Proposal</h3>
      <p className="mt-2 text-[color:var(--muted)]">
        Turn signals into a draft proposal with custom summary and diff.
      </p>
      <div className="mt-4 flex flex-wrap gap-3">
        <button className="cta cta-secondary" onClick={useLastSignal}>
          Use Last Signal
        </button>
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <label className="text-sm text-[color:var(--muted)]">
          Pathway ID (required)
          <input
            className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
            value={proposalPathwayId}
            onChange={(event) => setProposalPathwayId(event.target.value)}
          />
        </label>
        <label className="text-sm text-[color:var(--muted)]">
          Summary
          <input
            className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
            value={proposalSummary}
            onChange={(event) => setProposalSummary(event.target.value)}
            placeholder="Short summary of the proposed update"
          />
        </label>
      </div>
      <div className="mt-4">
        <label className="text-sm text-[color:var(--muted)]">
          Diff (JSON, optional)
          <textarea
            className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3 text-sm"
            value={proposalDiff}
            onChange={(event) => setProposalDiff(event.target.value)}
            placeholder='{"add":["New requirement"],"remove":["Old requirement"]}'
          />
        </label>
      </div>
      <div className="mt-6 flex flex-wrap items-center gap-3">
        <button
          className="cta"
          onClick={createProposal}
          disabled={!isLoggedIn || proposalSaving}
        >
          {proposalSaving ? "Creating..." : "Create Draft Proposal"}
        </button>
        {proposalMessage && (
          <span className="text-sm text-[color:var(--muted)]">
            {proposalMessage}
          </span>
        )}
      </div>

      <div className="divider" />

      <h3 className="text-xl font-semibold">Signals List + Copilot</h3>
      <p className="mt-2 text-[color:var(--muted)]">
        Select signals and let Copilot generate a structured draft proposal.
      </p>
      <div className="mt-4">
        <label className="text-sm text-[color:var(--muted)]">
          Copilot Instruction (optional)
          <textarea
            className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3 text-sm"
            value={copilotInstruction}
            onChange={(event) => setCopilotInstruction(event.target.value)}
            placeholder="Example: prioritize practical full-stack and cloud deployment evidence."
          />
        </label>
      </div>
      <div className="mt-4 flex flex-wrap gap-3">
        <button className="cta cta-secondary" onClick={loadSignals}>
          Refresh Signals
        </button>
        <button className="cta cta-secondary" onClick={selectAllSignals}>
          Select All
        </button>
        <button className="cta cta-secondary" onClick={clearAllSignals}>
          Clear
        </button>
        <button
          className="cta"
          onClick={createProposalFromSelected}
          disabled={!isLoggedIn || proposalSaving}
        >
          Create Copilot Proposal from Selected
        </button>
      </div>
      {signalsError && (
        <p className="mt-3 text-sm text-[color:var(--accent-2)]">
          {signalsError}
        </p>
      )}
      <div className="mt-6 grid gap-3">
        {signals.length === 0 && (
          <p className="text-sm text-[color:var(--muted)]">No signals yet.</p>
        )}
        {signals.map((signal) => (
          <div
            key={signal.id}
            className="flex flex-col gap-3 rounded-xl border border-[color:var(--border)] p-4 md:flex-row md:items-center md:justify-between"
          >
            <label className="flex items-start gap-3">
              <input
                type="checkbox"
                checked={Boolean(selectedSignals[signal.id])}
                onChange={() => toggleSignal(signal.id)}
              />
              <div>
                <p className="font-medium">
                  {signal.skill_name ?? "Unknown skill"}{" "}
                  {signal.role_family ? `- ${signal.role_family}` : ""}
                </p>
                <p className="text-sm text-[color:var(--muted)]">
                  {signal.frequency ?? "--"} freq - {signal.source_count ?? "--"} sources
                </p>
                <p className="text-xs text-[color:var(--muted)]">
                  Pathway: {signal.pathway_id ?? "n/a"} | Window:{" "}
                  {signal.window_start ?? "--"} {"->"} {signal.window_end ?? "--"}
                </p>
              </div>
            </label>
          </div>
        ))}
      </div>

      <div className="divider" />

      <h3 className="text-xl font-semibold">Proposal Workflow</h3>
      <p className="mt-2 text-[color:var(--muted)]">
        Review proposal drafts and approve when ready.
      </p>
      <div className="mt-4 flex flex-wrap gap-3">
        <button className="cta cta-secondary" onClick={loadProposals}>
          Refresh Proposals
        </button>
      </div>
      {proposalsError && (
        <p className="mt-3 text-sm text-[color:var(--accent-2)]">{proposalsError}</p>
      )}
      <div className="mt-6 grid gap-3">
        {proposals.length === 0 && (
          <p className="text-sm text-[color:var(--muted)]">
            No proposals available yet.
          </p>
        )}
        {proposals.map((proposal) => (
          <div
            key={proposal.id}
            className="rounded-xl border border-[color:var(--border)] p-4"
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="font-medium">{proposal.summary || "Draft proposal"}</p>
                <p className="text-xs text-[color:var(--muted)]">
                  Status: {proposal.status} | Pathway: {proposal.pathway_id}
                </p>
                <p className="text-xs text-[color:var(--muted)]">
                  Created: {new Date(proposal.created_at).toLocaleString()}
                  {proposal.approved_at
                    ? ` | Approved: ${new Date(proposal.approved_at).toLocaleString()}`
                    : ""}
                </p>
              </div>
              {proposal.status !== "approved" && (
                <button
                  className="cta"
                  onClick={() => approveProposal(proposal.id)}
                  disabled={approvingProposalId === proposal.id}
                >
                  {approvingProposalId === proposal.id ? "Approving..." : "Approve"}
                </button>
              )}
              {proposal.status === "approved" && (
                <button
                  className="cta"
                  onClick={() => publishProposal(proposal.id)}
                  disabled={publishingProposalId === proposal.id}
                >
                  {publishingProposalId === proposal.id ? "Publishing..." : "Publish"}
                </button>
              )}
            </div>
            <pre className="mt-3 max-h-56 overflow-auto rounded-lg border border-[color:var(--border)] p-3 text-xs text-[color:var(--muted)]">
              {JSON.stringify(proposal.diff ?? {}, null, 2)}
            </pre>
          </div>
        ))}
      </div>
    </section>
  );
}
