"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PageShell } from "@/components/page-shell";

const BACKEND = process.env.NEXT_PUBLIC_FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000";
const DEFAULT_ORG = "org-1";

type MemoryEntry = {
  key: string;
  value: string;
  workspace_id?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

type MemoryCandidate = {
  candidate_id: string;
  candidate_type: string;
  content: Record<string, string>;
  risk_level: string;
  created_at?: string | null;
};

function fmt(date: string | null | undefined): string {
  if (!date) return "—";
  try { return new Date(date).toLocaleDateString(); } catch { return date; }
}

export default function MemoryPage() {
  const [memories, setMemories] = useState<MemoryEntry[]>([]);
  const [candidates, setCandidates] = useState<MemoryCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [promotingId, setPromotingId] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setError("");
    Promise.all([
      fetch(`${BACKEND}/memories?org_id=${DEFAULT_ORG}&limit=200`).then((r) => r.json()),
      fetch(`${BACKEND}/memories/candidates?org_id=${DEFAULT_ORG}`).then((r) => r.json()).catch(() => ({ candidates: [] })),
    ])
      .then(([memData, candData]: [unknown, unknown]) => {
        const md = memData as { memories?: MemoryEntry[] };
        const cd = candData as { candidates?: MemoryCandidate[] };
        setMemories(Array.isArray(md?.memories) ? md.memories : []);
        setCandidates(Array.isArray(cd?.candidates) ? cd.candidates : []);
      })
      .catch(() => setError("Failed to load memories. Is the backend running?"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleDelete = async (key: string) => {
    setDeleting(key);
    try {
      await fetch(`${BACKEND}/memories/${DEFAULT_ORG}/${encodeURIComponent(key)}`, { method: "DELETE" });
      setMemories((prev) => prev.filter((m) => m.key !== key));
    } catch {
      setError(`Failed to delete memory: ${key}`);
    } finally {
      setDeleting(null);
      setConfirmDelete(null);
    }
  };

  const handlePromote = async (candidateId: string, approved: boolean) => {
    setPromotingId(candidateId);
    try {
      await fetch(`${BACKEND}/memories/candidates/promote`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ candidate_id: candidateId, approved }),
      });
      setCandidates((prev) => prev.filter((c) => c.candidate_id !== candidateId));
      if (approved) load();
    } catch {
      setError("Failed to process candidate.");
    } finally {
      setPromotingId(null);
    }
  };

  const filtered = filter.trim()
    ? memories.filter(
        (m) =>
          m.key.toLowerCase().includes(filter.toLowerCase()) ||
          m.value.toLowerCase().includes(filter.toLowerCase())
      )
    : memories;

  return (
    <PageShell
      title="Memory"
      subtitle="What Friday knows about your organization"
      breadcrumbs={[{ label: "Settings", href: "/settings" }, { label: "Memory" }]}
      headerActions={<button className="btn btn-secondary btn-sm" onClick={load}>Refresh</button>}
    >
      {error && (
        <div className="error-state" role="alert" style={{ padding: "1rem", marginBottom: "1rem" }}>
          ⚠️ {error}
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        <div className="card">
          <div className="card-body">
            <div style={{ display: "flex", gap: "0.75rem", alignItems: "flex-start" }}>
              <span style={{ fontSize: "1.5rem" }}>🧠</span>
              <div>
                <p style={{ margin: "0 0 0.25rem", fontWeight: 600, fontSize: "0.9375rem" }}>
                  About Friday&apos;s Memory
                </p>
                <p style={{ margin: 0, fontSize: "0.875rem", color: "var(--text-muted)", lineHeight: 1.6 }}>
                  Friday stores facts it learns about your organization and injects them as context in future
                  conversations. Workspace-scoped memories are only injected when you chat in that workspace.
                </p>
              </div>
            </div>
          </div>
        </div>

        {candidates.length > 0 && (
          <div className="card">
            <div className="card-header">
              Memory Candidates
              <span className="badge badge-accent" style={{ marginLeft: "0.5rem" }}>{candidates.length} pending</span>
            </div>
            <div className="card-body" style={{ padding: 0 }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Type</th><th>Content</th><th>Risk</th><th>Date</th><th style={{ width: 140 }} />
                  </tr>
                </thead>
                <tbody>
                  {candidates.map((c) => (
                    <tr key={c.candidate_id}>
                      <td>
                        <span className="badge badge-neutral" style={{ fontSize: "0.72rem" }}>
                          {c.candidate_type.replace(/_/g, " ")}
                        </span>
                      </td>
                      <td style={{ fontSize: "0.85rem", maxWidth: 320 }}>
                        {Object.entries(c.content || {}).slice(0, 3).map(([k, v]) => (
                          <span key={k} style={{ display: "block" }}>
                            <strong>{k}:</strong> {String(v).slice(0, 80)}
                          </span>
                        ))}
                      </td>
                      <td>
                        <span className={`badge ${c.risk_level === "high" ? "badge-danger" : "badge-neutral"}`}
                              style={{ fontSize: "0.72rem" }}>{c.risk_level}</span>
                      </td>
                      <td style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>{fmt(c.created_at)}</td>
                      <td>
                        <span style={{ display: "flex", gap: "0.375rem", justifyContent: "flex-end" }}>
                          <button className="btn btn-secondary btn-sm"
                                  onClick={() => handlePromote(c.candidate_id, false)}
                                  disabled={promotingId === c.candidate_id}>Dismiss</button>
                          <button className="btn btn-primary btn-sm"
                                  onClick={() => handlePromote(c.candidate_id, true)}
                                  disabled={promotingId === c.candidate_id}>
                            {promotingId === c.candidate_id ? "…" : "Approve"}
                          </button>
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        <div className="card">
          <div className="card-header">
            Stored Memories
            <span className="badge badge-neutral" style={{ marginLeft: "0.5rem" }}>{memories.length}</span>
          </div>
          <div className="card-body" style={{ padding: memories.length > 0 ? 0 : undefined }}>
            {loading ? (
              <div className="loading-skeleton">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="loading-skeleton-row" style={{ height: "3.5rem" }} />
                ))}
              </div>
            ) : memories.length === 0 ? (
              <div className="empty-state" style={{ padding: "2.5rem" }}>
                <div className="empty-state-icon">🧠</div>
                <p className="empty-state-title">No memories stored</p>
                <p className="empty-state-body">
                  Friday builds memory as you interact. Try asking it to remember something about your organization.
                </p>
                <Link href="/" className="btn btn-primary">Go to Chat</Link>
              </div>
            ) : (
              <>
                <div style={{ padding: "0.75rem 1rem", borderBottom: "1px solid var(--border)" }}>
                  <input className="form-input" type="search" placeholder="Filter by key or content…"
                         value={filter} onChange={(e) => setFilter(e.target.value)} style={{ maxWidth: 320 }} />
                </div>
                {filtered.length === 0 ? (
                  <p style={{ padding: "1.5rem", color: "var(--text-muted)", fontSize: "0.875rem" }}>
                    No memories match &ldquo;{filter}&rdquo;
                  </p>
                ) : (
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th style={{ width: "28%" }}>Key</th>
                        <th>Value</th>
                        <th style={{ width: "110px" }}>Scope</th>
                        <th style={{ width: "90px" }}>Added</th>
                        <th style={{ width: "80px" }} />
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.map((mem) => (
                        <tr key={mem.key}>
                          <td>
                            <code style={{ fontSize: "0.8125rem", background: "var(--surface)",
                              padding: "0.125rem 0.375rem", borderRadius: "0.25rem", fontFamily: "monospace" }}>
                              {mem.key}
                            </code>
                          </td>
                          <td style={{ fontSize: "0.875rem", lineHeight: 1.5 }}>
                            {String(mem.value).slice(0, 120)}{String(mem.value).length > 120 && "…"}
                          </td>
                          <td style={{ fontSize: "0.8rem" }}>
                            {mem.workspace_id
                              ? <span className="badge badge-neutral" style={{ fontSize: "0.7rem" }}>Workspace</span>
                              : <span style={{ color: "var(--text-muted)" }}>Global</span>}
                          </td>
                          <td style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                            {fmt(mem.created_at ?? mem.updated_at)}
                          </td>
                          <td style={{ textAlign: "right" }}>
                            {confirmDelete === mem.key ? (
                              <span style={{ display: "flex", gap: "0.375rem", justifyContent: "flex-end" }}>
                                <button className="btn btn-secondary btn-sm"
                                        onClick={() => setConfirmDelete(null)}>Cancel</button>
                                <button className="btn btn-danger btn-sm"
                                        onClick={() => handleDelete(mem.key)}
                                        disabled={deleting === mem.key}>
                                  {deleting === mem.key ? "…" : "Delete"}
                                </button>
                              </span>
                            ) : (
                              <button className="btn btn-ghost btn-sm" style={{ color: "#ef4444" }}
                                      onClick={() => setConfirmDelete(mem.key)}>Remove</button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </PageShell>
  );
}
