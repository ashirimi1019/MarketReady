"use client";

import { useSession } from "@/lib/session";
import { useState } from "react";
import Link from "next/link";
import { apiSend } from "@/lib/api";
import { formatDisplayName } from "@/lib/name";
import ThemeToggle from "@/components/ThemeToggle";
import { useRouter } from "next/navigation";

export default function NavBar() {
  const { username, isLoggedIn, logout, refreshToken } = useSession();
  const displayName = formatDisplayName(username);
  const router = useRouter();
  const [loggingOut, setLoggingOut] = useState(false);

  const handleLogout = async () => {
    if (loggingOut) return;
    setLoggingOut(true);
    try {
      if (refreshToken) {
        await apiSend("/auth/logout", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
      }
    } catch {
      // If API logout fails, still clear local session.
    } finally {
      if (username) {
        window.localStorage.removeItem(`mp_selection_${username}`);
      }
      logout();
      window.localStorage.removeItem("mp_admin_token");
      router.push("/login");
      setLoggingOut(false);
    }
  };

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
        <ThemeToggle />
        <button className="nav-pill nav-pill-muted" onClick={handleLogout} disabled={loggingOut}>
          {loggingOut ? "Logging out..." : "Logout"}
        </button>
      </div>
    </header>
  );
}
