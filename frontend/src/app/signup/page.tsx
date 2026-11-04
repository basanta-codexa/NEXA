"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { registerTenant } from "@/lib/api";

export default function SignupPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    name: "",
    description: "",
    adminEmail: "",
    adminPassword: "",
    inviteCode: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await registerTenant({
        name: form.name.trim(),
        description: form.description.trim(),
        adminEmail: form.adminEmail.trim().toLowerCase(),
        adminPassword: form.adminPassword,
        inviteCode: form.inviteCode.trim(),
      });
      router.push("/login?registered=1");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create tenant");
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
        <h1 className="auth-title">Create your workspace</h1>
        <p className="auth-sub">
          Tenant signup is invite-only. Get your invite code from a NEXA admin.
        </p>

        <form onSubmit={onSubmit}>
          <div className="field">
            <label className="label" htmlFor="name">Company / tenant name</label>
            <input id="name" className="input" placeholder="Acme Corp" value={form.name} onChange={set("name")} required />
          </div>
          <div className="field">
            <label className="label" htmlFor="description">Description (optional)</label>
            <input id="description" className="input" placeholder="What you'll build with NEXA" value={form.description} onChange={set("description")} />
          </div>
          <div className="field">
            <label className="label" htmlFor="adminEmail">Admin email</label>
            <input id="adminEmail" className="input" type="email" autoComplete="email" placeholder="admin@company.com" value={form.adminEmail} onChange={set("adminEmail")} required />
          </div>
          <div className="field">
            <label className="label" htmlFor="adminPassword">Admin password</label>
            <input id="adminPassword" className="input" type="password" autoComplete="new-password" placeholder="Min. 8 characters" value={form.adminPassword} onChange={set("adminPassword")} minLength={8} required />
          </div>
          <div className="field">
            <label className="label" htmlFor="inviteCode">Invite code</label>
            <input id="inviteCode" className="input mono" placeholder="nxa_…" value={form.inviteCode} onChange={set("inviteCode")} required />
          </div>
          {error ? <div className="error-text" style={{ marginBottom: 12 }}>{error}</div> : null}
          <button className="btn btn-primary" type="submit" disabled={loading} style={{ width: "100%", justifyContent: "center" }}>
            {loading ? "Creating workspace…" : "Create workspace"}
          </button>
        </form>

        <hr className="divider" />
        <p className="muted">
          Already have a workspace?{" "}
          <Link className="auth-link" href="/login">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
