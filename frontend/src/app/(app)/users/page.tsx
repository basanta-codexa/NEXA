"use client";

import { useEffect, useState, type FormEvent } from "react";
import PageHeader from "@/components/PageHeader";
import StatusBadge from "@/components/StatusBadge";
import EmptyState from "@/components/EmptyState";
import Modal from "@/components/Modal";
import {
  listUsers,
  createUser,
  getStoredUser,
  type TenantUser,
} from "@/lib/api";

export default function UsersPage() {
  const [users, setUsers] = useState<TenantUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modal, setModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ email: "", password: "", role: "member" });
  const [formError, setFormError] = useState<string | null>(null);

  const user = getStoredUser();
  const isAdmin = user?.role === "admin";

  const reload = async () => {
    try {
      const { users } = await listUsers();
      setUsers(users);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
  }, []);

  const onCreate = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setFormError(null);
    try {
      await createUser(form.email.trim().toLowerCase(), form.password, form.role);
      setModal(false);
      setForm({ email: "", password: "", role: "member" });
      await reload();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <PageHeader
        title="Team"
        subtitle="Members of this tenant workspace"
        actions={isAdmin ? <button className="btn btn-primary" onClick={() => setModal(true)}>+ Add member</button> : undefined}
      />

      <div className="content">
        {error ? <div className="error-text" style={{ marginBottom: 12 }}>{error}</div> : null}

        {loading ? (
          <div className="muted">Loading team…</div>
        ) : users.length === 0 ? (
          <EmptyState title="No team members" hint="Invite someone to collaborate on your agents." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Email</th><th>Role</th><th>Tenant</th><th>You</th></tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td style={{ fontWeight: 600 }}>{u.email}</td>
                    <td><StatusBadge status={u.role} /></td>
                    <td className="muted mono">#{u.tenant_id}</td>
                    <td className="muted">{u.id === user?.id ? "you" : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {modal ? (
        <Modal title="Add team member" onClose={() => setModal(false)}>
          <form onSubmit={onCreate}>
            <div className="field">
              <label className="label">Email</label>
              <input className="input" type="email" placeholder="member@company.com" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} required />
            </div>
            <div className="field">
              <label className="label">Password</label>
              <input className="input" type="password" autoComplete="new-password" placeholder="Min. 8 characters" value={form.password} onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} minLength={8} required />
            </div>
            <div className="field">
              <label className="label">Role</label>
              <select className="select" value={form.role} onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}>
                <option value="member">Member</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            {formError ? <div className="error-text" style={{ marginBottom: 10 }}>{formError}</div> : null}
            <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
              <button type="button" className="btn btn-ghost" onClick={() => setModal(false)}>Cancel</button>
              <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? "Adding…" : "Add member"}</button>
            </div>
          </form>
        </Modal>
      ) : null}
    </>
  );
}
