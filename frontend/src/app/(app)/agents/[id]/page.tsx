"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import PageHeader from "@/components/PageHeader";
import StatusBadge from "@/components/StatusBadge";
import {
  getAgent,
  updateAgent,
  setAgentStatus,
  deleteAgent,
  runAgent,
  getStoredUser,
  type Agent,
} from "@/lib/api";

export default function AgentDetailPage() {
  const params = useParams<{ id: string }>();
  const agentId = Number(params?.id);
  const router = useRouter();

  const [agent, setAgent] = useState<Agent | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const user = getStoredUser();
  const isAdmin = user?.role === "admin";

  const [message, setMessage] = useState("Hello! Briefly introduce yourself.");
  const [running, setRunning] = useState(false);
  const [runOutput, setRunOutput] = useState<string>("");
  const [runMeta, setRunMeta] = useState<string>("");

  const reload = async () => {
    try {
      setAgent(await getAgent(agentId));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!Number.isFinite(agentId)) return;
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agentId]);

  const onToggle = async () => {
    if (!agent) return;
    const next = agent.status === "active" ? "paused" : "active";
    try {
      await setAgentStatus(agent.id, next);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const onDelete = async () => {
    if (!agent) return;
    if (!window.confirm(`Delete agent "${agent.name}"? This cannot be undone.`)) return;
    try {
      await deleteAgent(agent.id);
      router.replace("/agents");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const onRun = async (e: FormEvent) => {
    e.preventDefault();
    if (!agent) return;
    if (agent.status !== "active") {
      setError("Agent must be active before it can run.");
      return;
    }
    setRunning(true);
    setRunOutput("");
    setRunMeta("");
    try {
      const result = await runAgent(agent.id, message);
      const r = result as Record<string, unknown>;
      setRunOutput(String(r.response ?? "(no response)"));
      setRunMeta(
        `Model: ${String(r.model ?? agent.model_name ?? "unknown")} · ` +
          `Steps: ${Array.isArray(r.steps) ? r.steps.length : 0} · ` +
          `Duration: ${String(r.duration_ms ?? "?")}ms`
      );
    } catch (err) {
      setRunOutput(
        `Error: ${err instanceof Error ? err.message : String(err)}`
      );
    } finally {
      setRunning(false);
    }
  };

  if (loading) {
    return (
      <>
        <PageHeader title="Agent" subtitle="Loading…" />
        <div className="content"><div className="muted">Loading agent details…</div></div>
      </>
    );
  }

  if (error && !agent) {
    return (
      <>
        <PageHeader title="Agent" subtitle="Not found" />
        <div className="content">
          <div className="error-text" style={{ marginBottom: 14 }}>{error}</div>
          <Link className="btn" href="/agents">← Back to agents</Link>
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title={agent?.name ?? "Agent"}
        subtitle={agent?.model_name ?? undefined}
        actions={
          <div style={{ display: "flex", gap: 8 }}>
            <Link className="btn" href="/agents">← Back</Link>
            {isAdmin && agent ? (
              <>
                <button className="btn" onClick={onToggle}>
                  {agent.status === "active" ? "Pause" : "Activate"}
                </button>
                <button className="btn btn-danger" onClick={onDelete}>Delete</button>
              </>
            ) : null}
          </div>
        }
      />

      <div className="content">
        {error ? <div className="error-text" style={{ marginBottom: 12 }}>{error}</div> : null}

        {agent ? (
          <div className="grid-2">
            {/* Configuration card */}
            <div className="card">
              <div className="card-title">Configuration</div>
              <dl style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "10px 18px", fontSize: 13 }}>
                <dt className="muted">Status</dt>
                <dd><StatusBadge status={agent.status} /></dd>
                <dt className="muted">Role</dt>
                <dd>{agent.role}</dd>
                <dt className="muted">Language</dt>
                <dd>{agent.language}</dd>
                <dt className="muted">Model</dt>
                <dd className="mono">{agent.model_name ?? "not set"}</dd>
                <dt className="muted">Description</dt>
                <dd>{agent.description || "—"}</dd>
                <dt className="muted">Temperature</dt>
                <dd>{agent.temperature ?? "default"}</dd>
                <dt className="muted">Max tokens</dt>
                <dd>{agent.max_tokens ?? "default"}</dd>
                <dt className="muted">Top-p</dt>
                <dd>{agent.top_p ?? "default"}</dd>
              </dl>

              {agent.system_prompt ? (
                <>
                  <hr className="divider" />
                  <div className="card-title">System prompt</div>
                  <div className="output" style={{ maxHeight: 180 }}>{agent.system_prompt}</div>
                </>
              ) : null}
            </div>

            {/* Playground */}
            <form className="card" onSubmit={onRun}>
              <div className="card-title">Live playground</div>

              <div className="field">
                <label className="label" htmlFor="msg">Message</label>
                <textarea
                  id="msg"
                  className="textarea"
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  required
                />
              </div>

              <button className="btn btn-primary" type="submit" disabled={running} style={{ width: "100%", justifyContent: "center" }}>
                {running ? "Thinking…" : "Send"}
              </button>

              {runOutput ? (
                <>
                  <hr className="divider" />
                  <div className="card-title">Response</div>
                  <div className="output">{runOutput}</div>
                  {runMeta ? <div className="muted" style={{ marginTop: 8, fontSize: 12 }}>{runMeta}</div> : null}
                </>
              ) : null}
            </form>
          </div>
        ) : null}
      </div>
    </>
  );
}
