"use client";

import { useEffect, useState, type FormEvent } from "react";
import PageHeader from "@/components/PageHeader";
import StatusBadge from "@/components/StatusBadge";
import Modal from "@/components/Modal";
import EmptyState from "@/components/EmptyState";
import {
  listAgents,
  createAgent,
  updateAgent,
  deleteAgent,
  setAgentStatus,
  getStoredUser,
  type Agent,
} from "@/lib/api";
import Link from "next/link";

const EMPTY_FORM = {
  name: "",
  role: "Assistant",
  language: "English",
  description: "",
  model_name: "ollama/llama3.2:3b",
  system_prompt: "You are a helpful voice assistant. Keep answers short and conversational.",
  temperature: 0.3,
  max_tokens: 300,
  top_p: 0.9,
};

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modal, setModal] = useState<"create" | "edit" | null>(null);
  const [editing, setEditing] = useState<Agent | null>(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const user = getStoredUser();
  const isAdmin = user?.role === "admin";

  const reload = async () => {
    setLoading(true);
    try {
      const { agents } = await listAgents();
      setAgents(agents);
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

  const openCreate = () => {
    setEditing(null);
    setForm({ ...EMPTY_FORM });
    setFormError(null);
    setModal("create");
  };

  const openEdit = (a: Agent) => {
    setEditing(a);
    setForm({
      name: a.name,
      role: a.role,
      language: a.language,
      description: a.description ?? "",
      model_name: a.model_name ?? "ollama/llama3.2:3b",
      system_prompt: a.system_prompt ?? "",
      temperature: a.temperature ?? 0.3,
      max_tokens: a.max_tokens ?? 300,
      top_p: a.top_p ?? 0.9,
    });
    setFormError(null);
    setModal("edit");
  };

  const onSave = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setFormError(null);
    const payload = {
      ...form,
      temperature: Number(form.temperature),
      max_tokens: Number(form.max_tokens),
      top_p: Number(form.top_p),
    };
    try {
      if (editing) {
        await updateAgent(editing.id, payload);
      } else {
        await createAgent(payload);
      }
      setModal(null);
      await reload();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  const onDelete = async (a: Agent) => {
    if (!window.confirm(`Delete agent "${a.name}"? This cannot be undone.`)) return;
    try {
      await deleteAgent(a.id);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const onToggle = async (a: Agent) => {
    const next = a.status === "active" ? "paused" : "active";
    try {
      await setAgentStatus(a.id, next);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <>
      <PageHeader
        title="Agents"
        subtitle="Create, configure and activate your AI agents"
        actions={isAdmin ? <button className="btn btn-primary" onClick={openCreate}>+ New agent</button> : undefined}
      />

      <div className="content">
        {error ? <div className="error-text" style={{ marginBottom: 12 }}>{error}</div> : null}

        {loading ? (
          <div className="muted">Loading agents…</div>
        ) : agents.length === 0 ? (
          <EmptyState
            icon="◎"
            title="No agents yet"
            hint="Create your first AI agent — it will appear here."
            action={isAdmin ? <button className="btn btn-primary" onClick={openCreate}>+ Create agent</button> : undefined}
          />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Model</th>
                  <th>Language</th>
                  <th>Status</th>
                  <th style={{ textAlign: "right" }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {agents.map((a) => (
                  <tr key={a.id}>
                    <td style={{ fontWeight: 600 }}>
                      <Link className="auth-link" href={`/agents/${a.id}`}>{a.name}</Link>
                    </td>
                    <td className="mono muted">{a.model_name ?? "not set"}</td>
                    <td className="muted">{a.language}</td>
                    <td><StatusBadge status={a.status} /></td>
                    <td>
                      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                        <Link className="btn btn-sm" href={`/agents/${a.id}`}>Open</Link>
                        {isAdmin ? (
                          <>
                            <button className="btn btn-sm" onClick={() => openEdit(a)}>Edit</button>
                            <button className="btn btn-sm" onClick={() => onToggle(a)}>
                              {a.status === "active" ? "Pause" : "Activate"}
                            </button>
                            <button className="btn btn-danger btn-sm" onClick={() => onDelete(a)}>Delete</button>
                          </>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {modal ? (
        <Modal title={editing ? `Edit ${editing.name}` : "Create agent"} onClose={() => setModal(null)}>
          <form onSubmit={onSave}>
            <div className="field">
              <label className="label">Name</label>
              <input className="input" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} required />
            </div>
            <div className="grid-split" style={{ gap: 10 }}>
              <div className="field">
                <label className="label">Role</label>
                <input className="input" value={form.role} onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))} />
              </div>
              <div className="field">
                <label className="label">Language</label>
                <input className="input" value={form.language} onChange={(e) => setForm((f) => ({ ...f, language: e.target.value }))} />
              </div>
            </div>
            <div className="field">
              <label className="label">Model</label>
              <select className="select" value={form.model_name} onChange={(e) => setForm((f) => ({ ...f, model_name: e.target.value }))}>
                <option value="ollama/llama3.2:3b">ollama/llama3.2:3b</option>
                <option value="ollama/qwen3:4b">ollama/qwen3:4b</option>
                <option value="groq/openai/gpt-oss-20b">groq/openai/gpt-oss-20b</option>
                <option value="xai/grok-4">xai/grok-4</option>
                <option value="gpt-4o-mini">gpt-4o-mini</option>
                <option value="fake">fake (offline test)</option>
              </select>
            </div>
            <div className="field">
              <label className="label">System prompt</label>
              <textarea className="textarea" value={form.system_prompt} onChange={(e) => setForm((f) => ({ ...f, system_prompt: e.target.value }))} />
            </div>
            {formError ? <div className="error-text" style={{ marginBottom: 10 }}>{formError}</div> : null}
            <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
              <button type="button" className="btn btn-ghost" onClick={() => setModal(null)}>Cancel</button>
              <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? "Saving…" : editing ? "Save changes" : "Create agent"}</button>
            </div>
          </form>
        </Modal>
      ) : null}
    </>
  );
}
