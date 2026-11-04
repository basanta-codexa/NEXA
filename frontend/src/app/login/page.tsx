"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { login } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email.trim(), password);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <Link href="/" className="brand" style={{ border: "none", marginBottom: 22 }}>
          <div className="brand-mark">N</div>
          <div>
            <div className="brand-name">NEXA</div>
            <div className="brand-sub">AI WORKFORCE</div>
          </div>
        </Link>
        <h1 className="auth-title">Welcome back</h1>
        <p className="auth-sub">Sign in to your tenant workspace.</p>

        <form onSubmit={onSubmit}>
          <div className="field">
            <label className="label" htmlFor="email">Email</label>
            <input
              id="email"
              className="input"
              type="email"
              autoComplete="email"
              placeholder="you@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label className="label" htmlFor="password">Password</label>
            <input
              id="password"
              className="input"
              type="password"
              autoComplete="current-password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {error ? <div className="error-text" style={{ marginBottom: 12 }}>{error}</div> : null}
          <button className="btn btn-primary" type="submit" disabled={loading} style={{ width: "100%", justifyContent: "center" }}>
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <hr className="divider" />
        <p className="muted">
          New tenant?{" "}
          <Link className="auth-link" href="/signup">
            Create a workspace with an invite
          </Link>
        </p>
      </div>
    </div>
  );
}
