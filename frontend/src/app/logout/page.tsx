"use client";

import { useEffect } from "react";
import { useLocalStorage } from "@/lib/useLocalStorage";
import { apiSend } from "@/lib/api";
import { useSession } from "@/lib/session";

export default function LogoutPage() {
  const [, setUsername] = useLocalStorage("mp_username", "");
  const [, setAuthToken] = useLocalStorage("mp_auth_token", "");
  const [, setRefreshToken] = useLocalStorage("mp_refresh_token", "");
  const [, setAdminToken] = useLocalStorage("mp_admin_token", "");
  const [, setLoggedIn] = useLocalStorage("mp_logged_in", "false");
  const { logout, username, refreshToken } = useSession();

  useEffect(() => {
    if (refreshToken) {
      apiSend("/auth/logout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      }).catch(() => null);
    }
    if (username) {
      window.localStorage.removeItem(`mp_selection_${username}`);
    }
    setUsername("");
    setAuthToken("");
    setRefreshToken("");
    setAdminToken("");
    setLoggedIn("false");
    logout();
  }, [setUsername, setAuthToken, setRefreshToken, setAdminToken, setLoggedIn, logout, username, refreshToken]);

  return (
    <section className="panel max-w-xl">
      <span className="badge">Session Cleared</span>
      <h2 className="mt-3 text-3xl font-semibold">Logged out</h2>
      <p className="mt-2 text-[color:var(--muted)]">
        Your local session has been cleared. Return to the login page to set a
        new session.
      </p>
      <div className="mt-6">
        <a className="cta" href="/login">
          Back to Login
        </a>
      </div>
    </section>
  );
}
