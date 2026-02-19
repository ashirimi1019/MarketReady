"use client";

import { useEffect, useState } from "react";
import { apiGet, apiSend } from "@/lib/api";
import { useLocalStorage } from "@/lib/useLocalStorage";
import { useSession } from "@/lib/session";

type Pathway = {
  id: string;
  name: string;
};

type ChecklistVersion = {
  id: string;
  pathway_id: string;
  version_number: number;
  status: string;
  published_at?: string | null;
  item_count: number;
};

type ChecklistItem = {
  id: string;
  title: string;
  tier: string;
  allowed_proof_types: string[];
};

type ChecklistChangeLog = {
  id: string;
  change_type: string;
  summary?: string | null;
  created_by?: string | null;
  created_at: string;
};

export default function AdminChecklistsPage() {
  const { isLoggedIn, username } = useSession();
  const [adminToken, setAdminToken] = useLocalStorage(
    "mp_admin_token",
    "change-me"
  );
  const [pathways, setPathways] = useState<Pathway[]>([]);
  const [versions, setVersions] = useState<ChecklistVersion[]>([]);
  const [items, setItems] = useState<ChecklistItem[]>([]);
  const [changeLogs, setChangeLogs] = useState<ChecklistChangeLog[]>([]);
  const [selectedPathway, setSelectedPathway] = useState("");
  const [selectedVersion, setSelectedVersion] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  const headers = { "X-Admin-Token": adminToken };

  useEffect(() => {
    if (!isLoggedIn) return;
    apiGet<Pathway[]>("/majors")
      .then((majors) => majors[0]?.id)
      .then((majorId) =>
        majorId ? apiGet<Pathway[]>(`/majors/${majorId}/pathways`) : Promise.resolve([])
      )
      .then((data) => setPathways(data))
      .catch(() => setPathways([]));
  }, [isLoggedIn]);

  const loadVersions = (pathwayId: string) => {
    apiGet<ChecklistVersion[]>(`/admin/checklists/${pathwayId}/versions`, headers)
      .then(setVersions)
      .catch(() => setVersions([]));
    apiGet<ChecklistChangeLog[]>(`/admin/checklists/${pathwayId}/changes`, headers)
      .then(setChangeLogs)
      .catch(() => setChangeLogs([]));
  };

  const loadItems = (versionId: string) => {
    apiGet<ChecklistItem[]>(
      `/admin/checklists/versions/${versionId}/items`,
      headers
    )
      .then(setItems)
      .catch(() => setItems([]));
  };

  const createDraft = async () => {
    if (!selectedPathway) return;
    try {
      await apiSend(`/admin/checklists/${selectedPathway}/draft`, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ items: [] }),
      });
      loadVersions(selectedPathway);
    } catch {
      setMessage("Failed to create draft.");
    }
  };

  const publishDraft = async () => {
    if (!selectedPathway) return;
    try {
      await apiSend(`/admin/checklists/${selectedPathway}/publish`, {
        method: "POST",
        headers,
      });
      loadVersions(selectedPathway);
    } catch {
      setMessage("Failed to publish draft.");
    }
  };

  const rollbackChecklist = async () => {
    if (!selectedPathway) return;
    try {
      await apiSend(`/admin/checklists/${selectedPathway}/rollback`, {
        method: "POST",
        headers,
      });
      setMessage("Rollback applied.");
      loadVersions(selectedPathway);
    } catch {
      setMessage("Failed to rollback checklist.");
    }
  };

  const updateItem = async (itemId: string, title: string) => {
    try {
      await apiSend(`/admin/checklists/items/${itemId}`, {
        method: "PUT",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });
      loadItems(selectedVersion);
    } catch {
      setMessage("Failed to update item.");
    }
  };

  const deleteItem = async (itemId: string) => {
    try {
      await apiSend(`/admin/checklists/items/${itemId}`, {
        method: "DELETE",
        headers,
      });
      loadItems(selectedVersion);
    } catch {
      setMessage("Failed to delete item.");
    }
  };

  return (
    <section className="panel">
      <h2 className="text-2xl font-semibold">Checklist Versions</h2>
      <p className="mt-2 text-[color:var(--muted)]">
        {isLoggedIn
          ? `Signed in as ${username}. Draft, publish, and audit checklist versions by pathway.`
          : "Log in to manage checklist versions safely."}
      </p>
      {!isLoggedIn && (
        <p className="mt-4 text-sm text-[color:var(--accent-2)]">
          Please log in before managing checklists.
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
      <div className="mt-6 grid gap-4 md:grid-cols-3">
        <select
          className="rounded-lg border border-[color:var(--border)] p-3"
          value={selectedPathway}
          onChange={(event) => {
            const value = event.target.value;
            setSelectedPathway(value);
            setSelectedVersion("");
            setItems([]);
            if (value) {
              loadVersions(value);
            }
          }}
        >
          <option value="">Select pathway</option>
          {pathways.map((pathway) => (
            <option key={pathway.id} value={pathway.id}>
              {pathway.name}
            </option>
          ))}
        </select>
        <button className="cta" onClick={createDraft}>
          Create Draft
        </button>
        <button className="cta cta-secondary" onClick={publishDraft}>
          Publish Draft
        </button>
        <button className="cta cta-secondary" onClick={rollbackChecklist}>
          Rollback
        </button>
      </div>
      {message && (
        <p className="mt-3 text-sm text-[color:var(--accent-2)]">{message}</p>
      )}
      <div className="mt-6 grid gap-4">
        {versions.map((version) => (
          <div
            key={version.id}
            className="flex items-center justify-between rounded-xl border border-[color:var(--border)] p-4"
          >
            <div>
              <p className="font-medium">
                v{version.version_number} - {version.status}
              </p>
              <p className="text-sm text-[color:var(--muted)]">
                {version.item_count} items
              </p>
            </div>
            <button
              className="cta cta-secondary"
              onClick={() => {
                setSelectedVersion(version.id);
                loadItems(version.id);
              }}
            >
              View Items
            </button>
          </div>
        ))}
      </div>
      {selectedVersion && (
        <div className="mt-8">
          <h3 className="text-lg font-semibold">Checklist Items</h3>
          <div className="mt-4 grid gap-3">
            {items.map((item) => (
              <div
                key={item.id}
                className="flex items-center justify-between rounded-xl border border-[color:var(--border)] p-4"
              >
                <div>
                  <p className="font-medium">{item.title}</p>
                  <p className="text-sm text-[color:var(--muted)]">{item.tier}</p>
                </div>
                <div className="flex gap-2">
                  <button
                    className="cta cta-secondary"
                    onClick={() => {
                      const title = window.prompt("Update title", item.title);
                      if (title) {
                        updateItem(item.id, title);
                      }
                    }}
                  >
                    Edit
                  </button>
                  <button
                    className="cta cta-secondary"
                    onClick={() => deleteItem(item.id)}
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
      {selectedPathway && (
        <div className="mt-8">
          <h3 className="text-lg font-semibold">Change Log</h3>
          <div className="mt-4 grid gap-3">
            {changeLogs.length === 0 && (
              <p className="text-sm text-[color:var(--muted)]">No changes logged yet.</p>
            )}
            {changeLogs.map((entry) => (
              <div key={entry.id} className="rounded-xl border border-[color:var(--border)] p-4">
                <p className="font-medium">
                  {entry.change_type}: {entry.summary || "No summary"}
                </p>
                <p className="text-xs text-[color:var(--muted)]">
                  {entry.created_by || "admin"} | {new Date(entry.created_at).toLocaleString()}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
