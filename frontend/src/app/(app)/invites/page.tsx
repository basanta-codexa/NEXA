"use client";

import { useEffect, useState, type FormEvent } from "react";
import PageHeader from "@/components/PageHeader";
import EmptyState from "@/components/EmptyState";
import {
  listInvites,
  createInvite,
  revokeInvite,
  getStoredUser,
  type InviteInfo,
} from "@/lib/api";

const EXPIRY_OPTIONS = [
  { value: 7, label: "7 days" },
  { value: 30, label: "30 days" },
  { value: 90, label: "90 days" },
  { value: 0, label: "Never expires" },
];

function statusClass(status: InviteInfo["status"]) {
  if (status === "active") return "badge badge-active";
  if (status === "expired") return "badge badge-paused";
  return "badge badge-archived";
}

async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // Fallback for non-secure contexts / older browsers
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(textarea);
    return ok;
  }
}

export default function InvitesPage() {
  const user = getStoredUser();
  const isAdmin = user?.role === "admin";

  const [invites, setInvites] = useState<InviteInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [description, setDescription] = useState("");
  const [expiresInDays, setExpiresInDays] = useState(7);
  const [creating, setCreating] = useState(false);
  const [newCode, setNewCode] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const reload = async () => {
    try {
      const { invites } = await listInvites();
      setInvites(invites);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onCreate = async (e: FormEvent) => {
    e.preventDefault();
    setCreating(true);
    setError(null);
    setNewCode(null);
    try {
      const res = await createInvite(description.trim(), expiresInDays);
      setNewCode(res.invite_code);
      setCopied(false);
      setDescription("");
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setCreating(false);
    }
  };

  const onCopy = async () => {
    if (!newCode) return;
    setCopied(await copyToClipboard(newCode));
  };

  const onRevoke = async (invite: InviteInfo) => {
    if (!window.confirm("Revoke this invite? It will no longer be usable.")) return;
    try {
      await revokeInvite(invite.id);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  if (!isAdmin) {
    return (
      <>
        <PageHeader title="Invites" subtitle="Restricted area" />
        <div className="content">
          <div className="card">
            <div className="error-text">Admin access only. Your role does not permit invite management.</div>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Invites"
        subtitle="Create one-time signup codes and track them"
      />

      <div className="content">
        {error ? <div className="error-text" style={{ marginBottom: 12 }}>{error}</div> : null}

        {/* Create */}
        <div className="card" style={{ marginBottom: 18 }}>
          <div className="card-title">Create invite</div>
          <form onSubmit={onCreate} style={{ display: "flex", gap: 10, alignItems: "flex-end", flexWrap: "wrap" }}>
            <div className="field" style={{ flex: "1 1 220px", marginBottom: 0 }}>
              <label className="label" htmlFor="desc">Description</label>
              <input
                id="desc"
                className="input"
                placeholder="Acme pilot — first customer"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
            <div className="field" style={{ marginBottom: 0 }}>
              <label className="label" htmlFor="expiry">Expiry</label>
              <select id="expiry" className="select" value={expiresInDays} onChange={(e) => setExpiresInDays(Number(e.target.value))}>
                {EXPIRY_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
            <button className="btn btn-primary" type="submit" disabled={creating}>
              {creating ? "Creating…" : "Generate invite"}
            </button>
          </form>

          {newCode ? (
            <>
              <hr className="divider" />
              <div className="card-title" style={{ color: "var(--amber)" }}>
                Copy this code now — it will not be shown again
              </div>
              <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                <code className="output" style={{ flex: "1 1 260px", maxHeight: "none" }}>{newCode}</code>
                <button className="btn btn-primary" onClick={onCopy} type="button">
                  {copied ? "Copied ✓" : "Copy"}
                </button>
              </div>
            </>
          ) : null}
        </div>

        {/* List */}
        <div className="card">
          <div className="card-title">All invites ({invites.length})</div>
          {loading ? (
            <div className="muted">Loading…</div>
          ) : invites.length === 0 ? (
            <EmptyState
              title="No invites yet"
              hint="Generate your first invite above. Each code is one-time and expires automatically."
            />
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Description</th>
                    <th>Created</th>
                    <th>Expires</th>
                    <th>Status</th>
                    <th style={{ textAlign: "right" }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {invites.map((inv) => (
                    <tr key={inv.id}>
                      <td style={{ fontWeight: 600 }}>{inv.description ?? "—"}</td>
                      <td className="muted">{new Date(inv.created_at).toLocaleDateString()}</td>
                      <td className="muted">{inv.expires_at ? new Date(inv.expires_at).toLocaleDateString() : "Never"}</td>
                      <td><span className={statusClass(inv.status)}>{inv.status}</span></td>
                      <td style={{ textAlign: "right" }}>
                        {inv.status === "active" ? (
                          <button className="btn btn-danger btn-sm" onClick={() => onRevoke(inv)}>
                            Revoke
                          </button>
                        ) : (
                          <span className="muted" style={{ fontSize: 12 }}>{inv.status === "used" ? "Redeemed" : "Expired"}</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
