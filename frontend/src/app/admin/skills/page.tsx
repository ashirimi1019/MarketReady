"use client";

import { useEffect, useState } from "react";
import { apiGet, apiSend } from "@/lib/api";
import { useLocalStorage } from "@/lib/useLocalStorage";
import { useSession } from "@/lib/session";

type Skill = {
  id: string;
  name: string;
  description?: string | null;
};

export default function AdminSkillsPage() {
  const { isLoggedIn, username } = useSession();
  const [adminToken, setAdminToken] = useLocalStorage(
    "mp_admin_token",
    "change-me"
  );
  const [skills, setSkills] = useState<Skill[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [newSkill, setNewSkill] = useState({ name: "", description: "" });

  const headers = { "X-Admin-Token": adminToken };

  const loadSkills = () => {
    apiGet<Skill[]>("/admin/skills", headers)
      .then(setSkills)
      .catch(() => setSkills([]));
  };

  useEffect(() => {
    if (isLoggedIn) {
      loadSkills();
    }
  }, []);

  const createSkill = async () => {
    setMessage(null);
    if (!newSkill.name.trim()) {
      setMessage("Skill name is required.");
      return;
    }
    try {
      await apiSend("/admin/skills", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(newSkill),
      });
      setNewSkill({ name: "", description: "" });
      loadSkills();
    } catch {
      setMessage("Failed to create skill.");
    }
  };

  const deleteSkill = async (id: string) => {
    try {
      await apiSend(`/admin/skills/${id}`, {
        method: "DELETE",
        headers,
      });
      loadSkills();
    } catch {
      setMessage("Failed to delete skill.");
    }
  };

  const updateSkill = async (id: string, name: string, description?: string) => {
    try {
      await apiSend(`/admin/skills/${id}`, {
        method: "PUT",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ name, description }),
      });
      loadSkills();
    } catch {
      setMessage("Failed to update skill.");
    }
  };

  const promptEdit = (skill: Skill) => {
    const name = window.prompt("Skill name", skill.name);
    if (!name) return;
    const description = window.prompt("Description", skill.description ?? "");
    updateSkill(skill.id, name, description ?? "");
  };

  return (
    <section className="panel">
      <h2 className="text-2xl font-semibold">Skills Library</h2>
      <p className="mt-2 text-[color:var(--muted)]">
        {isLoggedIn
          ? `Signed in as ${username}. Create, update, or archive skills used across pathways.`
          : "Log in to manage skills safely."}
      </p>
      {!isLoggedIn && (
        <p className="mt-4 text-sm text-[color:var(--accent-2)]">
          Please log in before making changes.
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
      <div className="mt-6 grid gap-3 md:grid-cols-3">
        <input
          className="rounded-lg border border-[color:var(--border)] p-3"
          placeholder="Skill name"
          value={newSkill.name}
          onChange={(event) =>
            setNewSkill({ ...newSkill, name: event.target.value })
          }
        />
        <input
          className="rounded-lg border border-[color:var(--border)] p-3"
          placeholder="Description"
          value={newSkill.description}
          onChange={(event) =>
            setNewSkill({ ...newSkill, description: event.target.value })
          }
        />
        <button className="cta" onClick={createSkill}>
          Add Skill
        </button>
      </div>
      {message && (
        <p className="mt-3 text-sm text-[color:var(--accent-2)]">{message}</p>
      )}
      <div className="mt-6 grid gap-3">
        {skills.map((skill) => (
          <div
            key={skill.id}
            className="flex items-center justify-between rounded-xl border border-[color:var(--border)] p-4"
          >
            <div>
              <p className="font-medium">{skill.name}</p>
              <p className="text-sm text-[color:var(--muted)]">
                {skill.description ?? "No description"}
              </p>
            </div>
            <div className="flex gap-2">
              <button
                className="cta cta-secondary"
                onClick={() => promptEdit(skill)}
              >
                Edit
              </button>
              <button
                className="cta cta-secondary"
                onClick={() => deleteSkill(skill.id)}
              >
                Delete
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
