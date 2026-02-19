"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiSend } from "@/lib/api";
import { useSession } from "@/lib/session";

type AuthResponse = {
  user_id: string;
  auth_token?: string | null;
  refresh_token?: string | null;
  email_verification_required?: boolean;
  message?: string | null;
};

type ActionResponse = {
  ok: boolean;
  message: string;
};

export default function LoginPage() {
  const { login } = useSession();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [forgotIdentity, setForgotIdentity] = useState("");
  const [resetCode, setResetCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const passwordPolicyHint =
    "Password must be at least 8 characters, include one uppercase letter, and one special character.";

  const handleLogin = async () => {
    if (!username.trim()) {
      setStatus("Username is required.");
      return;
    }
    if (!password.trim()) {
      setStatus("Password is required.");
      return;
    }
    setLoading(true);
    setStatus(null);
    try {
      const response = await apiSend<AuthResponse>("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: username.trim(),
          password,
        }),
      });
      if (!response.auth_token || !response.refresh_token) {
        setStatus(response.message ?? "Login blocked.");
        return;
      }
      login(response.user_id, response.auth_token, response.refresh_token);
      setPassword("");
      router.push("/");
    } catch (error) {
      setStatus(
        error instanceof Error ? error.message : "Login failed. Check credentials."
      );
    } finally {
      setLoading(false);
    }
  };

  const handleForgotPassword = async () => {
    if (!forgotIdentity.trim()) {
      setStatus("Enter username or email for password reset.");
      return;
    }
    const body = forgotIdentity.includes("@")
      ? { email: forgotIdentity.trim() }
      : { username: forgotIdentity.trim() };
    try {
      const response = await apiSend<ActionResponse>("/auth/password/forgot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      setStatus(response.message);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Reset request failed.");
    }
  };

  const handleResetPassword = async () => {
    if (!username.trim() || !resetCode.trim() || !newPassword.trim()) {
      setStatus("Enter username, reset code, and new password.");
      return;
    }
    if (newPassword.length < 8 || !/[A-Z]/.test(newPassword) || !/[^A-Za-z0-9]/.test(newPassword)) {
      setStatus(passwordPolicyHint);
      return;
    }
    try {
      const response = await apiSend<ActionResponse>("/auth/password/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: username.trim(),
          code: resetCode.trim(),
          new_password: newPassword,
        }),
      });
      setStatus(response.message);
      setResetCode("");
      setNewPassword("");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Password reset failed.");
    }
  };

  return (
    <section className="panel max-w-3xl">
      <span className="badge">Secure Access</span>
      <h2 className="mt-3 text-3xl font-semibold">Login</h2>
      <p className="mt-2 text-[color:var(--muted)]">
        Enter username/password. Password reset flow is available below.
      </p>

      <div className="mt-6 grid gap-4">
        <label className="text-sm text-[color:var(--muted)]">
          Username
          <input
            className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
        </label>
        <label className="text-sm text-[color:var(--muted)]">
          Password
          <input
            type="password"
            className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <button className="cta" onClick={handleLogin} disabled={loading}>
          {loading ? "Logging in..." : "Login"}
        </button>
      </div>

      <div className="divider" />

      <h3 className="text-xl font-semibold">Password Reset</h3>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <label className="text-sm text-[color:var(--muted)]">
          Username or Email
          <input
            className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
            value={forgotIdentity}
            onChange={(event) => setForgotIdentity(event.target.value)}
          />
        </label>
        <div className="flex items-end">
          <button className="cta cta-secondary w-full" onClick={handleForgotPassword}>
            Request Reset Code
          </button>
        </div>
        <label className="text-sm text-[color:var(--muted)]">
          Reset Code
          <input
            className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
            value={resetCode}
            onChange={(event) => setResetCode(event.target.value)}
          />
        </label>
        <label className="text-sm text-[color:var(--muted)]">
          New Password
          <input
            type="password"
            className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
          />
          <span className="mt-2 block text-xs text-[color:var(--muted)]">
            {passwordPolicyHint}
          </span>
        </label>
      </div>
      <div className="mt-4">
        <button className="cta cta-secondary" onClick={handleResetPassword}>
          Reset Password
        </button>
      </div>

      <div className="mt-4 grid gap-2">
        {status && <span className="text-sm text-[color:var(--muted)]">{status}</span>}
      </div>

      <p className="mt-4 text-sm text-[color:var(--muted)]">
        Need an account?{" "}
        <a className="text-[color:var(--accent-2)] underline" href="/register">
          Create one
        </a>
      </p>
    </section>
  );
}
