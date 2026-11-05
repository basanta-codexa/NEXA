"use client";

import { useEffect, useRef, useState, type FormEvent, type ChangeEvent } from "react";
import PageHeader from "@/components/PageHeader";
import EmptyState from "@/components/EmptyState";
import {
  listDocuments,
  uploadDocument,
  deleteDocument,
  searchKnowledge,
  getStoredUser,
  type DocumentItem,
  type SearchResult,
} from "@/lib/api";

export default function KnowledgePage() {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const user = getStoredUser();
  const isAdmin = user?.role === "admin";

  const reload = async () => {
    try {
      const { documents } = await listDocuments();
      setDocs(documents);
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

  const onUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      await uploadDocument(file);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const onDelete = async (doc: DocumentItem) => {
    if (!window.confirm(`Delete "${doc.title}" and its indexed chunks?`)) return;
    try {
      await deleteDocument(doc.id);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const onSearch = async (e: FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    setError(null);
    try {
      setResults(await searchKnowledge(query.trim(), 5));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSearching(false);
    }
  };

  return (
    <>
      <PageHeader
        title="Knowledge"
        subtitle="Upload documents, index them and ground your agents"
        actions={
          isAdmin ? (
            <>
              <input
                ref={fileRef}
                type="file"
                accept=".txt,.md,.csv,.pdf,.docx,.json"
                style={{ display: "none" }}
                onChange={onUpload}
              />
              <button className="btn btn-primary" onClick={() => fileRef.current?.click()} disabled={uploading}>
                {uploading ? "Uploading…" : "+ Upload document"}
              </button>
            </>
          ) : undefined
        }
      />

      <div className="content">
        {error ? <div className="error-text" style={{ marginBottom: 12 }}>{error}</div> : null}

        {/* Search */}
        <div className="card" style={{ marginBottom: 18 }}>
          <div className="card-title">Semantic search</div>
          <form onSubmit={onSearch} style={{ display: "flex", gap: 10 }}>
            <input
              className="input"
              placeholder="Ask a question about your knowledge base…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              required
            />
            <button className="btn btn-primary" type="submit" disabled={searching}>
              {searching ? "Searching…" : "Search"}
            </button>
          </form>
          {results.length > 0 ? (
            <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 10 }}>
              {results.map((r) => (
                <div key={r.chunk_id} className="card card-tight" style={{ background: "var(--panel-2)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                    <strong style={{ fontSize: 13 }}>{r.title}</strong>
                    <span className="mono muted" style={{ fontSize: 11 }}>score {r.similarity.toFixed(3)} · chunk {r.chunk_index}</span>
                  </div>
                  <p className="muted" style={{ marginTop: 6, fontSize: 13 }}>{r.content}</p>
                </div>
              ))}
            </div>
          ) : null}
        </div>

        {/* Documents list */}
        <div className="card">
          <div className="card-title">Documents ({docs.length})</div>
          {loading ? (
            <div className="muted">Loading…</div>
          ) : docs.length === 0 ? (
            <EmptyState
              title="No documents yet"
              hint="Upload your first document — NEXA will chunk and index it automatically."
            />
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>Title</th><th>Uploaded</th><th style={{ textAlign: "right" }}>Actions</th></tr>
                </thead>
                <tbody>
                  {docs.map((d) => (
                    <tr key={d.id}>
                      <td style={{ fontWeight: 600 }}>{d.title}</td>
                      <td className="muted">{d.created_at ? new Date(d.created_at).toLocaleString() : "—"}</td>
                      <td style={{ textAlign: "right" }}>
                        {isAdmin ? <button className="btn btn-danger btn-sm" onClick={() => onDelete(d)}>Delete</button> : null}
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
