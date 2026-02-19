"use client";

import { useSession } from "@/lib/session";
import { useEffect, useState } from "react";
import Link from "next/link";
import { API_BASE } from "@/lib/api";
import { formatDisplayName } from "@/lib/name";
import ThemeToggle from "@/components/ThemeToggle";

export default function NavBar() {
  const { username, isLoggedIn } = useSession();
  const displayName = formatDisplayName(username);
  const [aiEnabled, setAiEnabled] = useState<boolean | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/meta/ai`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) {
          setAiEnabled(Boolean(data.ai_enabled));
        }
      })
      .catch(() => setAiEnabled(null));
  }, []);

  if (!isLoggedIn) {
    return (
      <header className="nav nav-guest">
        <div className="nav-left-cluster">
          <Link href="/" className="brand-pill">
            Market Ready
          </Link>
          <span className="nav-tagline">
            Proof-based career readiness
          </span>
        </div>
        <div className="nav-links">
          <Link href="/">Home</Link>
          <Link href="/#student-flow">Student Flow</Link>
          <Link href="/login">Login</Link>
          <Link href="/register">Register</Link>
        </div>
        <div className="nav-auth-meta">
          <ThemeToggle />
        </div>
      </header>
    );
  }

  return (
    <header className="nav nav-auth">
      <div className="nav-auth-left">
        <div className="badge">Student Command</div>
        <div className="nav-auth-title">Welcome, {displayName}</div>
        <div className="nav-auth-sub">
          Your personalized readiness hub and proof tracker.
        </div>
      </div>
      <div className="nav-auth-actions">
        <Link className="nav-pill" href="/student/onboarding">
          My Pathway
        </Link>
        <Link className="nav-pill" href="/student/profile">
          Profile
        </Link>
        <Link className="nav-pill" href="/student/checklist">
          Submit Proof
        </Link>
        <Link className="nav-pill" href="/student/proofs">
          My Proofs
        </Link>
        <Link className="nav-pill" href="/student/guide">
          AI Guide
        </Link>
        <Link className="nav-pill" href="/student/engagement">
          Goals
        </Link>
        <Link className="nav-pill" href="/student/readiness">
          Readiness Score
        </Link>
        <Link className="nav-pill" href="/student/timeline">
          Timeline
        </Link>
      </div>
      <div className="nav-auth-meta">
        <ThemeToggle />
        <span className="chip">
          AI {aiEnabled === null ? "Unknown" : aiEnabled ? "On" : "Off"}
        </span>
        <Link className="nav-pill nav-pill-muted" href="/logout">
          Logout
        </Link>
      </div>
    </header>
  );
}
