"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageShell } from "@/components/page-shell";

const BACKEND = process.env.NEXT_PUBLIC_FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000";

type ProcessDoc = {
  id: string;
  process_name: string;
  version: string;
  status: string;
  completeness_score: number;
  updated_at: string;
  roles: string[];
  trigger: string;
};

type HealthStats = {
  total_processes: number;
  avg_completeness: number;
  stale_count: number;
  draft_count: number;
  active_count: number;
  missing_owners_count: number;
  low_completeness_count: number;
};

function CompletenessRing({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = pct >= 80 ? "var(--success)" : pct >= 50 ? "#c47d00" : "var(--danger)";
  return (
    <span
      className="completeness-ring"
      style={{ "--ring-color": color, "--ring-pct": `${pct}%` } as React.CSSProperties}
      aria-label={`Completeness: ${pct}%`}
      title={`${pct}% complete`}
    >
      {pct}%
    </span>
  );
}

function StatusChip({ status }: { status: string }) {
  return <span className={`status-chip status-${status}`}>{status}</span>;
}

export default function ProcessesPage() {
  const [docs, setDocs] = useState<ProcessDoc[]>([]);
  const [health, setHealth] = useState<HealthStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "draft" | "active" | "deprecated">("all");

  useEffect(() => {
    Promise.all([
      fetch(`${BACKEND}/processes`).then((r) => r.json()),
      fetch(`${BACKEND}/processes/analytics`).then((r) => r.json()),
    ])
      .then(([docsData, healthData]: [unknown, unknown]) => {
        setDocs(Array.isArray(docsData) ? (docsData as ProcessDoc[]) : []);
        setHealth(healthData as HealthStats);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const filtered = filter === "all" ? docs : docs.filter((d) => d.status === filter);

  return (
    <PageShell
      title="Process Library"
      subtitle="Document, version, and govern your business processes"
      headerActions={
        <Link href="/" className="btn btn-primary">+ Map New Process</Link>
      }
    >
      {health && (
        <div className="stat-card-row">
          <div className="stat-card">
            <div className="stat-card-label">Total</div>
            <div className="stat-card-value">{health.total_processes}</div>
          </div>
          <div className="stat-card">
            <div className="stat-card-label">Active</div>
            <div className="stat-card-value" style={{ color: "#16a34a" }}>{health.active_count}</div>
          </div>
          <div className="stat-card">
            <div className="stat-card-label">Draft</div>
            <div className="stat-card-value" style={{ color: "#d97706" }}>{health.draft_count}</div>
          </div>
          <div className="stat-card">
            <div className="stat-card-label">Avg Completeness</div>
            <div className="stat-card-value">{Math.round(health.avg_completeness * 100)}%</div>
          </div>
          {health.stale_count > 0 && (
            <div className="stat-card">
              <div className="stat-card-label">Stale (90d+)</div>
              <div className="stat-card-value" style={{ color: "#dc2626" }}>{health.stale_count}</div>
            </div>
          )}
        </div>
      )}

      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1.25rem" }} role="group" aria-label="Filter by status">
        {(["all", "active", "draft", "deprecated"] as const).map((f) => (
          <button
            key={f}
            className={`btn ${filter === f ? "btn-primary" : "btn-secondary"} btn-sm`}
            onClick={() => setFilter(f)}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="loading-skeleton">
          {[...Array(4)].map((_, i) => <div key={i} className="loading-skeleton-row" style={{ height: "6rem", borderRadius: "0.75rem" }} />)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">⚙️</div>
          <p className="empty-state-title">No processes yet</p>
          <p className="empty-state-body">Ask Friday to map your first business process.</p>
          <Link href="/" className="btn btn-primary">Start Mapping</Link>
        </div>
      ) : (
        <ul className="process-grid" aria-label="Process list" style={{ listStyle: "none", padding: 0, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "1rem" }}>
          {filtered.map((doc) => (
            <li key={doc.id} className="card">
              <Link href={`/processes/${doc.id}`} style={{ textDecoration: "none", display: "block" }}>
                <div className="card-header" style={{ justifyContent: "space-between" }}>
                  <span style={{ fontWeight: 600, color: "var(--text)", fontSize: "0.9375rem" }}>{doc.process_name}</span>
                  <CompletenessRing score={doc.completeness_score} />
                </div>
                <div className="card-body" style={{ paddingTop: "0.75rem" }}>
                  <p style={{ fontSize: "0.8125rem", color: "var(--text-muted)", marginBottom: "0.75rem" }}>
                    {doc.trigger ? `↳ ${doc.trigger}` : "No trigger defined"}
                  </p>
                  <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
                    <StatusChip status={doc.status} />
                    <span className="badge badge-neutral">v{doc.version}</span>
                    {doc.roles.length > 0 && (
                      <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                        {doc.roles.slice(0, 2).join(", ")}{doc.roles.length > 2 ? ` +${doc.roles.length - 2}` : ""}
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.5rem" }}>
                    Updated {new Date(doc.updated_at).toLocaleDateString()}
                  </div>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </PageShell>
  );
}
