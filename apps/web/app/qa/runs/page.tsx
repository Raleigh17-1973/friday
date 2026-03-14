"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { PageShell } from "../../../components/page-shell";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Run {
  run_id: string;
  suite_id: string;
  title: string;
  environment: string;
  triggered_by: string;
  run_type: string;
  started_at: string;
  completed_at: string | null;
  status: string;
  pass_count: number;
  fail_count: number;
  blocked_count: number;
  not_run_count: number;
}

const STATUS_COLORS: Record<string, string> = {
  in_progress: "#b45309",
  completed: "#16a34a",
  aborted: "#dc2626",
};

function PassBar({ run }: { run: Run }) {
  const total = run.pass_count + run.fail_count + run.blocked_count + run.not_run_count;
  if (total === 0) return null;
  const passPct = Math.round((run.pass_count / total) * 100);
  const failPct = Math.round((run.fail_count / total) * 100);
  const blockedPct = Math.round((run.blocked_count / total) * 100);
  return (
    <div style={{ display: "flex", height: 6, borderRadius: 3, overflow: "hidden", background: "var(--surface-2)", marginTop: 6 }}>
      <div style={{ width: `${passPct}%`, background: "#16a34a" }} title={`Pass: ${run.pass_count}`} />
      <div style={{ width: `${failPct}%`, background: "#dc2626" }} title={`Fail: ${run.fail_count}`} />
      <div style={{ width: `${blockedPct}%`, background: "#b45309" }} title={`Blocked: ${run.blocked_count}`} />
    </div>
  );
}

export default function RunsPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${BACKEND}/qa/runs?org_id=default&limit=50`)
      .then((r) => r.ok ? r.json() : [])
      .then(setRuns)
      .catch(() => setRuns([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <PageShell
      title="Test Runs"
      subtitle="Execution history across all test suites"
      breadcrumbs={[{ label: "QA Registry", href: "/qa" }, { label: "Runs" }]}
      headerActions={
        <Link href="/qa/suites">
          <button style={{ padding: "7px 16px", borderRadius: 8, border: "1px solid var(--line)", background: "var(--surface)", color: "var(--text)", fontSize: "0.85rem", cursor: "pointer" }}>
            Go to Suites →
          </button>
        </Link>
      }
    >
      <div style={{ padding: "20px 28px" }}>
        {loading ? (
          <div style={{ color: "var(--muted)", padding: "40px 0", textAlign: "center" }}>Loading…</div>
        ) : runs.length === 0 ? (
          <div style={{ textAlign: "center", padding: "60px 0" }}>
            <div style={{ fontSize: "2.5rem", marginBottom: 12 }}>▶</div>
            <div style={{ fontWeight: 600, fontSize: "1.1rem", marginBottom: 6 }}>No test runs yet</div>
            <div style={{ color: "var(--muted)", marginBottom: 20, fontSize: "0.9rem" }}>
              Start a run from any test suite to begin recording results.
            </div>
            <Link href="/qa/suites">
              <button style={{ padding: "9px 20px", borderRadius: 8, border: "none", background: "var(--accent)", color: "#fff", fontSize: "0.875rem", fontWeight: 600, cursor: "pointer" }}>
                View Suites
              </button>
            </Link>
          </div>
        ) : (
          <div style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 12, overflow: "hidden" }}>
            {/* Header */}
            <div style={{
              display: "grid", gridTemplateColumns: "1fr 120px 100px 80px 80px 120px",
              padding: "8px 16px", background: "var(--surface-2)", borderBottom: "1px solid var(--line)",
              fontSize: "0.72rem", fontWeight: 700, color: "var(--muted)",
              textTransform: "uppercase", letterSpacing: "0.05em",
            }}>
              <span>Run</span>
              <span>Environment</span>
              <span>Status</span>
              <span style={{ textAlign: "center" }}>Pass</span>
              <span style={{ textAlign: "center" }}>Fail</span>
              <span>Started</span>
            </div>

            {runs.map((run, i) => {
              const statusColor = STATUS_COLORS[run.status] ?? "var(--muted)";
              const total = run.pass_count + run.fail_count + run.blocked_count + run.not_run_count;
              return (
                <Link key={run.run_id} href={`/qa/runs/${run.run_id}`} style={{ textDecoration: "none" }}>
                  <div
                    style={{
                      display: "grid", gridTemplateColumns: "1fr 120px 100px 80px 80px 120px",
                      padding: "12px 16px", borderBottom: i < runs.length - 1 ? "1px solid var(--line)" : "none",
                      alignItems: "center",
                    }}
                    onMouseOver={(e) => { (e.currentTarget as HTMLElement).style.background = "var(--surface-2)"; }}
                    onMouseOut={(e) => { (e.currentTarget as HTMLElement).style.background = "transparent"; }}
                  >
                    <div>
                      <div style={{ fontWeight: 600, fontSize: "0.875rem", color: "var(--text)", marginBottom: 2 }}>{run.title}</div>
                      <div style={{ fontSize: "0.72rem", color: "var(--muted)" }}>{run.triggered_by} · {total} tests</div>
                      <PassBar run={run} />
                    </div>
                    <div style={{ fontSize: "0.8rem", color: "var(--muted)", textTransform: "capitalize" }}>{run.environment}</div>
                    <div>
                      <span style={{ background: `${statusColor}18`, color: statusColor, border: `1px solid ${statusColor}40`, borderRadius: 6, padding: "2px 8px", fontSize: "0.72rem", fontWeight: 600, textTransform: "capitalize" }}>
                        {run.status.replace(/_/g, " ")}
                      </span>
                    </div>
                    <div style={{ textAlign: "center", fontWeight: 700, fontSize: "0.875rem", color: run.pass_count > 0 ? "#16a34a" : "var(--muted)" }}>
                      {run.pass_count}
                    </div>
                    <div style={{ textAlign: "center", fontWeight: 700, fontSize: "0.875rem", color: run.fail_count > 0 ? "#dc2626" : "var(--muted)" }}>
                      {run.fail_count}
                    </div>
                    <div style={{ fontSize: "0.78rem", color: "var(--muted)" }}>
                      {new Date(run.started_at).toLocaleDateString()}
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </PageShell>
  );
}
