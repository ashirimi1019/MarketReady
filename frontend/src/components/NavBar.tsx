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
  const [mobileOpen, setMobileOpen] = useState(false);

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
      // silent
    } finally {
      if (username) window.localStorage.removeItem(`mp_selection_${username}`);
      logout();
      window.localStorage.removeItem("mp_admin_token");
      router.push("/login");
      setLoggingOut(false);
    }
  };

  if (!isLoggedIn) {
    return (
      <header className="nav" data-testid="nav-guest">
        <div className="nav-brand-stack">
          <Link href="/" className="brand-pill" data-testid="nav-brand">
            Market Ready
          </Link>
          <span className="nav-tagline hidden sm:inline">Proof-first career readiness</span>
        </div>

        <nav className="nav-links nav-links-main" data-testid="nav-links-guest">
          <Link href="/#audit-engine" data-testid="nav-career-check">Career Check</Link>
          <Link href="/#signals" data-testid="nav-proof-vault">Proof Vault</Link>
          <Link href="/student/onboarding" data-testid="nav-my-plan">My Plan</Link>
        </nav>

        <div className="nav-auth-meta nav-auth-meta-guest">
          <ThemeToggle />
          <Link className="nav-pill nav-pill-muted" href="/login" data-testid="nav-login-btn">
            Login
          </Link>
          <Link className="nav-pill nav-pill-primary" href="/register" data-testid="nav-register-btn">
            Get Started
          </Link>
        </div>
      </header>
    );
  }

  return (
    <header className="nav nav-shell-auth" data-testid="nav-auth">
      <div className="nav-brand-stack">
        <Link href="/" className="brand-pill" data-testid="nav-brand-auth">
          Market Ready
        </Link>
        <span className="nav-tagline hidden md:inline">
          {displayName}
        </span>
      </div>

      {/* Desktop nav */}
      <nav className="nav-links nav-links-main hidden md:flex" data-testid="nav-links-auth">
        <Link href="/student/profile" data-testid="nav-profile">Profile</Link>
        <Link href="/student/checklist" data-testid="nav-checklist">Tasks</Link>
        <Link href="/student/readiness" data-testid="nav-readiness">My Score</Link>
        <Link href="/student/onboarding" data-testid="nav-onboarding">My Plan</Link>
        <Link href="/student/proofs" data-testid="nav-proofs">Proof Vault</Link>
        <Link href="/student/interview" data-testid="nav-interview">Interview AI</Link>
        <Link href="/student/resume-architect" data-testid="nav-skill-gap">Skill Gap</Link>
        <Link href="/student/guide" data-testid="nav-mission">Market Mission</Link>
      </nav>

      {/* Mobile toggle */}
      <button
        className="nav-pill md:hidden"
        onClick={() => setMobileOpen((v) => !v)}
        aria-label="Toggle menu"
        data-testid="nav-mobile-toggle"
      >
        Menu
      </button>

      <div className="nav-auth-meta">
        <ThemeToggle />
        <button
          className="nav-pill nav-pill-muted"
          onClick={handleLogout}
          disabled={loggingOut}
          data-testid="nav-logout-btn"
        >
          {loggingOut ? "..." : "Logout"}
        </button>
      </div>

      {/* Mobile dropdown */}
      {mobileOpen && (
        <div className="w-full md:hidden pt-2 pb-1 border-t border-[color:var(--border)] mt-2">
          <nav className="flex flex-col gap-1" data-testid="nav-mobile-menu">
            {[
              ["/student/profile", "Profile"],
              ["/student/checklist", "My Tasks"],
              ["/student/readiness", "My Score"],
              ["/student/onboarding", "My Plan"],
              ["/student/proofs", "Proof Vault"],
              ["/student/interview", "Interview AI"],
              ["/student/resume-architect", "Skill Gap Builder"],
              ["/student/guide", "Market Mission"],
            ].map(([href, label]) => (
              <Link
                key={href}
                href={href}
                className="px-3 py-2 rounded-lg text-sm text-[color:var(--muted)] hover:text-[color:var(--foreground)] hover:bg-[rgba(61,109,255,0.08)] transition-colors"
                onClick={() => setMobileOpen(false)}
              >
                {label}
              </Link>
            ))}
          </nav>
        </div>
      )}
    </header>
  );
}
