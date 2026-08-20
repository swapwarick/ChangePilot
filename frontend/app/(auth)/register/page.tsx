"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { signUp } from "@/lib/auth-client";
import { useAuth } from "@/lib/auth-context";

export default function RegisterPage() {
  const router = useRouter();
  const { refreshUser } = useAuth();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password !== confirm) {
      setError("Passwords do not match");
      return;
    }
    setLoading(true);
    try {
      await signUp(username, password, email || undefined);
      await refreshUser();
      router.push("/");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  const storageInfo = [
    { label: "30 MB persistent storage", icon: "💾" },
    { label: "Scan results saved across sessions", icon: "📊" },
    { label: "Unlimited GitHub repo scans", icon: "🔁" },
    { label: "AI-powered risk reports", icon: "✨" },
  ];

  return (
    <div className="auth-page">
      <div className="auth-card auth-card-wide">
        {/* Header */}
        <div className="auth-header">
          <div className="auth-logo">
            <img src="/logo.jpg" alt="ChangePilot" style={{ width: 56, height: 56, borderRadius: 14, objectFit: "cover" }} />
          </div>
          <h1 className="auth-title">Create your account</h1>
          <p className="auth-subtitle">Free forever · 30 MB persistent storage</p>
        </div>

        {/* Storage perks */}
        <div className="auth-perks">
          {storageInfo.map((item) => (
            <div key={item.label} className="auth-perk">
              <span className="auth-perk-icon">{item.icon}</span>
              <span className="auth-perk-label">{item.label}</span>
            </div>
          ))}
        </div>

        {/* Form */}
        <form onSubmit={handleRegister} className="auth-form">
          {error && (
            <div className="auth-error" role="alert">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              {error}
            </div>
          )}

          <div className="auth-row">
            <div className="auth-field">
              <label htmlFor="reg-username" className="auth-label">Username <span className="auth-required">*</span></label>
              <input
                id="reg-username"
                type="text"
                className="auth-input"
                placeholder="your_username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                minLength={3}
                maxLength={40}
                autoComplete="username"
                autoFocus
              />
            </div>

            <div className="auth-field">
              <label htmlFor="reg-email" className="auth-label">Email <span className="auth-optional">(optional)</span></label>
              <input
                id="reg-email"
                type="email"
                className="auth-input"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
              />
            </div>
          </div>

          <div className="auth-row">
            <div className="auth-field">
              <label htmlFor="reg-password" className="auth-label">Password <span className="auth-required">*</span></label>
              <input
                id="reg-password"
                type="password"
                className="auth-input"
                placeholder="Min. 8 characters"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                autoComplete="new-password"
              />
            </div>

            <div className="auth-field">
              <label htmlFor="reg-confirm" className="auth-label">Confirm Password <span className="auth-required">*</span></label>
              <input
                id="reg-confirm"
                type="password"
                className="auth-input"
                placeholder="Repeat password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                required
                autoComplete="new-password"
              />
            </div>
          </div>

          <button
            id="register-submit"
            type="submit"
            className="auth-btn auth-btn-primary"
            disabled={loading}
          >
            {loading ? (
              <span className="auth-btn-inner">
                <span className="auth-spinner" />
                Creating account…
              </span>
            ) : (
              "Create free account"
            )}
          </button>
        </form>

        {/* Footer */}
        <p className="auth-footer">
          Already have an account?{" "}
          <Link href="/login" className="auth-link">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
