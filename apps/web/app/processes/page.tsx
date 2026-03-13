"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

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
    <main className="processes-page">
      <header className="processes-header">
        <div>
          <h1>Process Library</h1>
          <p className="processes-subtitle">
            Document, version, and govern your business processes
          </p>
        </div>
        <Link href="/" className="new-process-btn">
          + Map New Process
        </Link>
      </header>

      {health && (
        <section className="health-bar" aria-label="Library health summary">
          <div className="health-stat">
            <span className="health-num">{health.total_processes}</span>
            <span className="health-label">Total</span>
          </div>
          <div className="health-stat">
            <span className="health-num">{Math.round(health.avg_completeness * 100)}%</span>
            <span className="health-label">Avg completeness</span>
          </div>
          <div className="health-stat">
            <span className="health-num">{health.active_count}</span>
            <span className="health-label">Active</span>
          </div>
          <div className="health-stat">
            <span className="health-num">{health.draft_count}</span>
            <span className="health-label">Draft</span>
          </div>
          {health.stale_count > 0 && (
            <div className="health-stat health-warn">
              <span className="health-num">{health.stale_count}</span>
              <span className="health-label">Stale (90d+)</span>
            </div>
          )}
          {health.low_completeness_count > 0 && (
            <div className="health-stat health-warn">
              <span className="health-num">{health.low_completeness_count}</span>
              <span className="health-label">Incomplete</span>
            </div>
          )}
        </section>
      )}

      <div className="processes-filter" role="group" aria-label="Filter by status">
        {(["all", "active", "draft", "deprecated"] as const).map((f) => (
          <button
            key={f}
            className={filter === f ? "filter-btn active" : "filter-btn"}
            onClick={() => setFilter(f)}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="processes-empty">Loading…</p>
      ) : filtered.length === 0 ? (
        <div className="processes-empty">
          <p>No processes yet.</p>
          <Link href="/">Ask Friday to map your first process →</Link>
        </div>
      ) : (
        <ul className="process-grid" aria-label="Process list">
          {filtered.map((doc) => (
            <li key={doc.id} className="process-card">
              <Link href={`/processes/${doc.id}`} className="process-card-link">
                <div className="process-card-top">
                  <h2 className="process-card-name">{doc.process_name}</h2>
                  <CompletenessRing score={doc.completeness_score} />
                </div>
                <p className="process-card-trigger">
                  {doc.trigger ? `↳ ${doc.trigger}` : "No trigger defined"}
                </p>
                <div className="process-card-meta">
                  <StatusChip status={doc.status} />
                  <span className="process-version">v{doc.version}</span>
                  {doc.roles.length > 0 && (
                    <span className="process-roles">
                      {doc.roles.slice(0, 2).join(", ")}
                      {doc.roles.length > 2 ? ` +${doc.roles.length - 2}` : ""}
                    </span>
                  )}
                </div>
                <time className="process-updated" dateTime={doc.updated_at}>
                  Updated {new Date(doc.updated_at).toLocaleDateString()}
                </time>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
