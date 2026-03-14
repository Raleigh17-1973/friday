"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PageShell } from "@/components/page-shell";

const BACKEND = process.env.NEXT_PUBLIC_FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000";
const DEFAULT_ORG = "org-1";

type MemoryEntry = { key: string; value: string };

export default function MemoryPage() {
  const [memories, setMemories] = useState<MemoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  const load = () => {
    setLoading(true);
    setError("");
    fetch(`${BACKEND}/memories?org_id=${DEFAULT_ORG}`)
      .then((r) => {
        if (!r.ok) throw new Error("Failed to load memories");
        return r.json();
      })
      .then((data: { memories: MemoryEntry[] }) => {
        setMemories(Array.isArray(data?.memories) ? data.memories : []);
      })
      .catch(() => setError("Failed to load memories. Is the backend running?"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleDelete = async (key: string) => {
    setDeleting(key);
    try {
      const res = await fetch(`${BACKEND}/memories/${DEFAULT_ORG}/${encodeURIComponent(key)}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("Failed to delete");
      setMemories((prev) => prev.filter((m) => m.key !== key));
    } catch {
      setError(`Failed to delete memory: ${key}`);
    } finally {
      setDeleting(null);
      setConfirmDelete(null);
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
      breadcrumbs={[
        { label: "Settings", href: "/settings" },
        { label: "Memory" },
      ]}
      headerActions={
        <button className="btn btn-secondary btn-sm" onClick={load}>
          Refresh
        </button>
      }
    >
      {error && (
        <div className="error-state" role="alert" style={{ padding: "1rem", marginBottom: "1rem" }}>
          ⚠️ {error}
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        {/* Explainer */}
        <div className="card">
          <div className="card-body">
            <div style={{ display: "flex", gap: "0.75rem", alignItems: "flex-start" }}>
              <span style={{ fontSize: "1.5rem" }}>🧠</span>
              <div>
                <p style={{ margin: "0 0 0.25rem", fontWeight: 600, fontSize: "0.9375rem" }}>
                  About Friday's Memory
                </p>
                <p style={{ margin: 0, fontSize: "0.875rem", color: "var(--text-muted)", lineHeight: 1.6 }}>
                  Friday stores facts it learns about your organization — pricing, team preferences, strategic
                  priorities — and injects them as context in future conversations. You can review and remove
                  any memory here.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Memory list */}
        <div className="card">
          <div className="card-header">
            Stored Memories
            <span className="badge badge-neutral" style={{ marginLeft: "0.5rem" }}>
              {memories.length}
            </span>
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
                  Friday builds memory as you interact. Try asking it to remember something about your
                  organization.
                </p>
                <Link href="/" className="btn btn-primary">
                  Go to Chat
                </Link>
              </div>
            ) : (
              <>
                <div style={{ padding: "0.75rem 1rem", borderBottom: "1px solid var(--border)" }}>
                  <input
                    className="form-input"
                    type="search"
                    placeholder="Filter memories…"
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                    style={{ maxWidth: 320 }}
                  />
                </div>
                {filtered.length === 0 ? (
                  <p style={{ padding: "1.5rem", color: "var(--text-muted)", fontSize: "0.875rem" }}>
                    No memories match &ldquo;{filter}&rdquo;
                  </p>
                ) : (
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th style={{ width: "35%" }}>Key</th>
                        <th>Value</th>
                        <th style={{ width: "80px" }} />
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.map((mem) => (
                        <tr key={mem.key}>
                          <td>
                            <code
                              style={{
                                fontSize: "0.8125rem",
                                background: "var(--surface)",
                                padding: "0.125rem 0.375rem",
                                borderRadius: "0.25rem",
                                fontFamily: "monospace",
                              }}
                            >
                              {mem.key}
                            </code>
                          </td>
                          <td style={{ fontSize: "0.875rem", lineHeight: 1.5 }}>{mem.value}</td>
                          <td style={{ textAlign: "right" }}>
                            {confirmDelete === mem.key ? (
                              <span style={{ display: "flex", gap: "0.375rem", justifyContent: "flex-end" }}>
                                <button
                                  className="btn btn-secondary btn-sm"
                                  onClick={() => setConfirmDelete(null)}
                                >
                                  Cancel
                                </button>
                                <button
                                  className="btn btn-danger btn-sm"
                                  onClick={() => handleDelete(mem.key)}
                                  disabled={deleting === mem.key}
                                >
                                  {deleting === mem.key ? "Deleting…" : "Delete"}
                                </button>
                              </span>
                            ) : (
                              <button
                                className="btn btn-ghost btn-sm"
                                style={{ color: "#ef4444" }}
                                onClick={() => setConfirmDelete(mem.key)}
                              >
                                Remove
                              </button>
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
