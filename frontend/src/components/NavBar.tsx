"use client";

import { useSession } from "@/lib/session";
import { useState, useEffect } from "react";
import Link from "next/link";
import { apiSend, apiGet } from "@/lib/api";
import { formatDisplayName } from "@/lib/name";
import ThemeToggle from "@/components/ThemeToggle";
import { useRouter } from "next/navigation";

type Notification = {
  id: string;
  kind: string;
  message: string;
  is_read: boolean;
  metadata?: Record<string, unknown> | null;
  created_at: string;
};

function NotificationBell({ onOpen }: { onOpen: () => void }) {
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    apiGet<Notification[]>("/user/notifications")
      .then(notes => setUnread(notes.filter(n => !n.is_read).length))
      .catch(() => setUnread(0));
  }, []);

  return (
    <button
      onClick={onOpen}
      className="relative nav-pill"
      aria-label="Notifications"
      data-testid="notification-bell"
    >
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
        <path d="M13.73 21a2 2 0 0 1-3.46 0" />
      </svg>
      {unread > 0 && (
        <span className="absolute -top-1 -right-1 h-4 w-4 rounded-full bg-[color:var(--danger)] text-white text-[9px] font-bold flex items-center justify-center"
          data-testid="notification-unread-count">
          {unread > 9 ? "9+" : unread}
        </span>
      )}
    </button>
  );
}

function NotificationPanel({ onClose }: { onClose: () => void }) {
  const [notes, setNotes] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);

  const load = () => {
    setLoading(true);
    apiGet<Notification[]>("/user/notifications")
      .then(setNotes).catch(() => setNotes([])).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const markRead = async (id: string) => {
    await apiSend(`/user/notifications/${id}/read`, { method: "POST" }).catch(() => {});
    setNotes(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n));
  };

  const runSentinel = async () => {
    setRunning(true);
    await apiSend("/sentinel/run", { method: "POST" }).catch(() => {});
    await load();
    setRunning(false);
  };

  const kindColor: Record<string, string> = {
    market_shift: "var(--accent)",
    market_pulse: "var(--primary)",
    skills_trend: "var(--success)",
    profile_tip: "var(--warning)",
  };

  const kindLabel: Record<string, string> = {
    market_shift: "⚡ Market Shift",
    market_pulse: "Market Pulse",
    skills_trend: "Skills Trend",
    profile_tip: "Profile Tip",
  };

  return (
    <div className="fixed inset-0 z-50" onClick={onClose}>
      <div
        className="absolute right-4 top-16 w-80 rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)] shadow-xl overflow-hidden"
        onClick={e => e.stopPropagation()}
        data-testid="notification-panel"
      >
        <div className="flex items-center justify-between p-4 border-b border-[color:var(--border)]">
          <h3 className="font-semibold text-sm">Sentinel Alerts</h3>
          <button
            onClick={runSentinel}
            disabled={running}
            className="text-xs text-[color:var(--primary)] hover:opacity-80 transition-opacity"
            data-testid="sentinel-run-btn"
          >
            {running ? "Scanning..." : "Run Scan"}
          </button>
        </div>
        <div className="max-h-80 overflow-y-auto">
          {loading ? (
            <div className="p-4 text-sm text-[color:var(--muted)] text-center animate-pulse">Loading...</div>
          ) : notes.length === 0 ? (
            <div className="p-4 text-sm text-[color:var(--muted)] text-center">No alerts yet. Run a scan!</div>
          ) : (
            notes.slice(0, 15).map(note => (
              <div
                key={note.id}
                className={`p-3 border-b border-[color:var(--border)] cursor-pointer hover:bg-[rgba(61,109,255,0.04)] transition-colors ${note.is_read ? "opacity-60" : ""}`}
                onClick={() => markRead(note.id)}
                data-testid={`notification-${note.id}`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full"
                    style={{ background: `${kindColor[note.kind] || "var(--primary)"}22`, color: kindColor[note.kind] || "var(--primary)" }}>
                    {kindLabel[note.kind] || note.kind}
                  </span>
                  {!note.is_read && <span className="h-1.5 w-1.5 rounded-full bg-[color:var(--primary)] ml-auto" />}
                </div>
                <p className="text-xs text-[color:var(--muted)] leading-relaxed">{note.message}</p>
                {note.metadata && (note.metadata as { action?: string }).action && (
                  <p className="text-xs text-[color:var(--primary)] mt-1 font-medium">
                    Action: {(note.metadata as { action?: string }).action}
                  </p>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

export default function NavBar() {
  const { username, isLoggedIn, logout, refreshToken } = useSession();
  const displayName = formatDisplayName(username);
  const router = useRouter();
  const [loggingOut, setLoggingOut] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);

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
    <>
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
        <nav className="nav-links nav-links-main hidden md:flex overflow-x-auto" style={{ scrollbarWidth: "none" }} data-testid="nav-links-auth">
          <Link href="/student/profile" data-testid="nav-profile" style={{ fontSize: "12px", whiteSpace: "nowrap" }}>Profile</Link>
          <Link href="/student/checklist" data-testid="nav-checklist" style={{ fontSize: "12px", whiteSpace: "nowrap" }}>Tasks</Link>
          <Link href="/student/readiness" data-testid="nav-readiness" style={{ fontSize: "12px", whiteSpace: "nowrap" }}>MRI Score</Link>
          <Link href="/student/kanban" data-testid="nav-kanban" style={{ fontSize: "12px", whiteSpace: "nowrap" }}>90-Day Plan</Link>
          <Link href="/student/onboarding" data-testid="nav-onboarding" style={{ fontSize: "12px", whiteSpace: "nowrap" }}>My Plan</Link>
          <Link href="/student/proofs" data-testid="nav-proofs" style={{ fontSize: "12px", whiteSpace: "nowrap" }}>Proof Vault</Link>
          <Link href="/student/interview" data-testid="nav-interview" style={{ fontSize: "12px", whiteSpace: "nowrap" }}>Interview AI</Link>
          <Link href="/student/resume-architect" data-testid="nav-skill-gap" style={{ fontSize: "12px", whiteSpace: "nowrap" }}>Skill Gap</Link>
          <Link href="/student/guide" data-testid="nav-mission" style={{ fontSize: "12px", whiteSpace: "nowrap" }}>Market Mission</Link>
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
          <NotificationBell onOpen={() => setNotifOpen(v => !v)} />
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
                ["/student/readiness", "MRI Score"],
                ["/student/kanban", "90-Day Kanban"],
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

      {notifOpen && <NotificationPanel onClose={() => setNotifOpen(false)} />}
    </>
  );
}
