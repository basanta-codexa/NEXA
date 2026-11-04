"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import PageHeader from "@/components/PageHeader";
import StatusBadge from "@/components/StatusBadge";
import {
  health,
  listAgents,
  listDocuments,
  listUsers,
  type Agent,
} from "@/lib/api";

export default function DashboardPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [docCount, setDocCount] = useState(0);
  const [userCount, setUserCount] = useState(0);
  const [dbOk, setDbOk] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [a, d, u, h] = await Promise.allSettled([
          listAgents(),
          listDocuments(),
          listUsers(),
          health(),
        ]);
        if (cancelled) return;
        if (a.status === "fulfilled") setAgents(a.value.agents);
        if (d.status === "fulfilled") setDocCount(d.value.documents.length);
        if (u.status === "fulfilled") setUserCount(u.value.users.length);
        if (h.status === "fulfilled") setDbOk(h.value.status === "ok");
        else setDbOk(false);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const active = agents.filter((a) => a.status === "active").length;

  return (
    <>
      <PageHeader
        title="Dashboard"
        subtitle="Your tenant at a glance"
        actions={
          <Link className="btn btn-primary" href="/agents">
            + New agent
          </Link>
        }
      />

      <div className="content">
        {error ? <div className="error-text" style={{ marginBottom: 16 }}>{error}</div> : null}

        {/* Stats */}
        <div className="stat-grid">
          <div className="stat">
            <div className="stat-value">{loading ? "–" : agents.length}</div>
            <div className="stat-label">Agents</div>
          </div>
          <div className="stat">
            <div className="stat-value" style={{ color: "var(--green)" }}>
              {loading ? "–" : active}
            </div>
            <div className="stat-label">Active agents</div>
          </div>
          <div className="stat">
            <div className="stat-value">{loading ? "–" : docCount}</div>
            <div className="stat-label">Knowledge documents</div>
          </div>
          <div className="stat">
            <div className="stat-value">{loading ? "–" : userCount}</div>
            <div className="stat-label">Team members</div>
          </div>
        </div>

        <div className="grid-2">
          {/* Recent agents */}
          <div className="card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <div className="card-title" style={{ marginBottom: 0 }}>Your agents</div>
              <Link className="auth-link" href="/agents">View all →</Link>
            </div>
            {agents.length === 0 && !loading ? (
              <div className="muted" style={{ padding: "12px 0" }}>
                No agents yet. <Link className="auth-link" href="/agents">Create your first agent</Link>
              </div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Model</th>
                      <th>Status</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {agents.slice(0, 5).map((a) => (
                      <tr key={a.id}>
                        <td style={{ fontWeight: 600 }}>{a.name}</td>
                        <td className="mono muted">{a.model_name ?? "not set"}</td>
                        <td><StatusBadge status={a.status} /></td>
                        <td>
                          <Link className="auth-link" href={`/agents/${a.id}`}>Open →</Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* System + quick start */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div className="card">
              <div className="card-title">System status</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span className="muted">API</span>
                  <span className="badge badge-active">Reachable</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span className="muted">PostgreSQL</span>
                  {dbOk === null ? (
                    <span className="muted">Checking…</span>
                  ) : dbOk ? (
                    <span className="badge badge-active">Healthy</span>
                  ) : (
                    <span className="badge badge-archived">Unavailable</span>
                  )}
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span className="muted">LLM providers</span>
                  <span className="badge badge-draft">Ollama / OpenAI / Groq / xAI</span>
                </div>
              </div>
            </div>

            <div className="card">
              <div className="card-title">Quick start</div>
              <ol style={{ paddingLeft: 18, display: "flex", flexDirection: "column", gap: 8, fontSize: 13 }}>
                <li><Link className="auth-link" href="/agents">Create an agent</Link> with a system prompt</li>
                <li>Upload knowledge in the <Link className="auth-link" href="/knowledge">Knowledge tab</Link></li>
                <li>Activate the agent and open its playground</li>
              </ol>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
