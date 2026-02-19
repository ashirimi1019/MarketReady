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

export default function RegisterPage() {
  const { login } = useSession();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const passwordPolicyHint =
    "Password must be at least 8 characters, include one uppercase letter, and one special character.";

  const handleRegister = async () => {
    if (!username.trim()) {
      setStatus("Username is required.");
      return;
    }
    if (!password.trim()) {
      setStatus("Password is required.");
      return;
    }
    if (password.length < 8) {
      setStatus(passwordPolicyHint);
      return;
    }
    if (!/[A-Z]/.test(password)) {
      setStatus(passwordPolicyHint);
      return;
    }
    if (!/[^A-Za-z0-9]/.test(password)) {
      setStatus(passwordPolicyHint);
      return;
    }
    if (password !== confirmPassword) {
      setStatus("Passwords do not match.");
      return;
    }

    setLoading(true);
    setStatus(null);
    try {
      const response = await apiSend<AuthResponse>("/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: username.trim(),
          email: email.trim() || null,
          password,
        }),
      });
      if (response.auth_token && response.refresh_token) {
        login(response.user_id, response.auth_token, response.refresh_token);
        router.push("/");
      } else if (response.email_verification_required) {
        setStatus(
          response.message ??
            "Account created. Verify your email code from the login page before signing in."
        );
      } else {
        setStatus("Registration completed. Please login.");
      }
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Registration failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="panel max-w-2xl">
      <span className="badge">Create Account</span>
      <h2 className="mt-3 text-3xl font-semibold">Register</h2>
      <p className="mt-2 text-[color:var(--muted)]">
        Create credentials for this app. You will be signed in automatically.
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
          Email
          <input
            type="email"
            className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
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
          <span className="mt-2 block text-xs text-[color:var(--muted)]">
            {passwordPolicyHint}
          </span>
        </label>
        <label className="text-sm text-[color:var(--muted)]">
          Confirm Password
          <input
            type="password"
            className="mt-2 w-full rounded-lg border border-[color:var(--border)] p-3"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
          />
        </label>
      </div>
      <div className="mt-6 flex flex-wrap items-center gap-3">
        <button className="cta" onClick={handleRegister} disabled={loading}>
          {loading ? "Creating account..." : "Create Account"}
        </button>
        {status && <span className="text-sm text-[color:var(--muted)]">{status}</span>}
      </div>
      <p className="mt-4 text-sm text-[color:var(--muted)]">
        Already registered?{" "}
        <a className="text-[color:var(--accent-2)] underline" href="/login">
          Login here
        </a>
      </p>
    </section>
  );
}
