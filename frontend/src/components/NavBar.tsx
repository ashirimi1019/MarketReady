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
      <header className="nav nav-shell">
        <div className="nav-brand-stack">
          <Link href="/" className="brand-pill">
            Market Ready
          </Link>
          <span className="nav-tagline">Proof-first career acceleration</span>
        </div>
        <nav className="nav-links nav-links-main">
          <Link href="/#audit-engine">Audit</Link>
          <Link href="/#signals">Signals</Link>
          <Link href="/student/onboarding">Portal</Link>
        </nav>
        <div className="nav-auth-meta nav-auth-meta-guest">
          <Link className="nav-pill nav-pill-muted" href="/login">
            Login
          </Link>
          <Link className="nav-pill nav-pill-muted" href="/register">
            Register
          </Link>
          <ThemeToggle />
        </div>
      </header>
    );
  }

  return (
    <header className="nav nav-shell nav-shell-auth">
      <div className="nav-brand-stack">
        <Link href="/" className="brand-pill">
          Market Ready
        </Link>
        <span className="nav-tagline">Signed in as {displayName}</span>
      </div>
      <nav className="nav-links nav-links-main">
        <Link href="/student/checklist">Audit</Link>
        <Link href="/student/readiness">Signals</Link>
        <Link href="/student/onboarding">Portal</Link>
        <Link href="/student/proofs">Vault</Link>
        <Link href="/student/interview">Interview</Link>
        <Link href="/student/resume-architect">Resume OpenAI</Link>
        <Link href="/student/guide">Guide</Link>
      </nav>
      <div className="nav-auth-meta">
        <span className="chip">
          OpenAI {aiEnabled === null ? "Unknown" : aiEnabled ? "On" : "Off"}
        </span>
        <ThemeToggle />
        <Link className="nav-pill nav-pill-muted" href="/logout">
          Logout
        </Link>
      </div>
    </header>
  );
}
