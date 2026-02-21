"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
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
  const [statusIsError, setStatusIsError] = useState(false);
  const [loading, setLoading] = useState(false);

  const passwordPolicyHint = "Min 8 chars, one uppercase, one special character.";

  const setMsg = (msg: string, error = true) => {
    setStatus(msg);
    setStatusIsError(error);
  };

  const handleRegister = async () => {
    if (!username.trim()) return setMsg("Username is required.");
    if (!password.trim()) return setMsg("Password is required.");
    if (password.length < 8 || !/[A-Z]/.test(password) || !/[^A-Za-z0-9]/.test(password))
      return setMsg(passwordPolicyHint);
    if (password !== confirmPassword) return setMsg("Passwords do not match.");

    setLoading(true);
    setStatus(null);
    try {
      const res = await apiSend<AuthResponse>("/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: username.trim(), email: email.trim() || null, password }),
      });
      if (res.auth_token && res.refresh_token) {
        login(res.user_id, res.auth_token, res.refresh_token);
        router.push("/");
      } else if (res.email_verification_required) {
        setMsg(res.message ?? "Account created. Verify your email before signing in.", false);
      } else {
        setMsg("Account created. Please log in.", false);
      }
    } catch (error) {
      setMsg(error instanceof Error ? error.message : "Registration failed.");
    } finally {
      setLoading(false);
    }
  };

  const inputClass = "w-full rounded-xl border px-4 py-3 text-sm outline-none transition-shadow";
  const inputStyle = { borderColor: "var(--input-border)", background: "var(--input-bg)", color: "var(--foreground)" };

  const strength =
    password.length === 0
      ? null
      : password.length < 6
        ? { label: "Weak", pct: 25, color: "var(--danger)" }
        : password.length < 8 || !/[A-Z]/.test(password)
          ? { label: "Fair", pct: 55, color: "var(--warning)" }
          : /[^A-Za-z0-9]/.test(password)
            ? { label: "Strong", pct: 100, color: "var(--success)" }
            : { label: "Good", pct: 80, color: "var(--primary)" };

  return (
    <div className="flex items-start justify-center pt-8 px-4">
      <div
        className="w-full max-w-md rounded-2xl border p-8"
        style={{ borderColor: "var(--border-hi)", background: "rgba(8,12,30,0.75)", backdropFilter: "blur(20px)" }}
        data-testid="register-page"
      >
        <div className="mb-8">
          <span className="badge mb-4 inline-flex" data-testid="register-badge">Create Account</span>
          <h1 className="text-2xl font-bold mt-3 tracking-tight">Get started</h1>
          <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
            Create your account to begin your market readiness journey.
          </p>
        </div>

        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-mono uppercase tracking-widest" style={{ color: "var(--muted)" }}>
              Username
            </label>
            <input
              className={inputClass}
              style={inputStyle}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
              data-testid="register-username-input"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-mono uppercase tracking-widest" style={{ color: "var(--muted)" }}>
              Email <span style={{ color: "var(--muted)", fontWeight: 400 }}>(optional)</span>
            </label>
            <input
              type="email"
              className={inputClass}
              style={inputStyle}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              data-testid="register-email-input"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-mono uppercase tracking-widest" style={{ color: "var(--muted)" }}>
              Password
            </label>
            <input
              type="password"
              className={inputClass}
              style={inputStyle}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              data-testid="register-password-input"
            />
            {strength && (
              <div className="flex items-center gap-2 mt-1">
                <div className="flex-1 h-1 rounded-full" style={{ background: "var(--border)" }}>
                  <div
                    className="h-1 rounded-full"
                    style={{ width: `${strength.pct}%`, background: strength.color }}
                  />
                </div>
                <span className="text-xs" style={{ color: strength.color }}>{strength.label}</span>
              </div>
            )}
            <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>{passwordPolicyHint}</p>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-mono uppercase tracking-widest" style={{ color: "var(--muted)" }}>
              Confirm Password
            </label>
            <input
              type="password"
              className={inputClass}
              style={inputStyle}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              data-testid="register-confirm-input"
            />
          </div>
        </div>

        <button
          className="cta w-full mt-6"
          onClick={handleRegister}
          disabled={loading}
          data-testid="register-submit-btn"
        >
          {loading ? "Creating account..." : "Create Account"}
        </button>

        {status && (
          <div
            className="mt-4 rounded-xl px-4 py-3 text-sm border"
            style={{
              background: statusIsError ? "rgba(255,59,48,0.08)" : "rgba(0,200,150,0.08)",
              borderColor: statusIsError ? "rgba(255,59,48,0.25)" : "rgba(0,200,150,0.25)",
              color: statusIsError ? "#ff6b8a" : "var(--success)",
            }}
            data-testid="register-status"
          >
            {status}
          </div>
        )}

        <p className="mt-5 text-sm text-center" style={{ color: "var(--muted)" }}>
          Already registered?{" "}
          <Link href="/login" style={{ color: "var(--primary)" }} data-testid="register-login-link">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
