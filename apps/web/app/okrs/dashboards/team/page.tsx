"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { PageShell } from "@/components/page-shell";

const BACKEND = process.env.NEXT_PUBLIC_FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000";
const HEALTH_COLOR: Record<string, string> = { green: "#22c55e", yellow: "#eab308", red: "#ef4444" };

function TeamDashboardContent() {
  const searchParams = useSearchParams();
  const nodeId = searchParams.get("node_id") ?? "node-company";
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`${BACKEND}/okrs/dashboard/team/${nodeId}`)
      .then(r => r.json()).then(setData).catch(() => setData(null)).finally(() => setLoading(false));
  }, [nodeId]);

  if (loading) return <p>Loading…</p>;
  if (!data) return <p>Unable to load team dashboard.</p>;

  const objectives = (data.objectives as unknown[]) ?? [];
  const overdue = (data.overdue_checkins as unknown[]) ?? [];

  return (
    <div>
      {/* Objectives */}
      <div className="card" style={{ padding: "var(--space-3)", marginBottom: "var(--space-3)" }}>
        <div style={{ fontSize: "0.875rem", fontWeight: 600, marginBottom: "var(--space-2)" }}>Active Objectives ({objectives.length})</div>
        {objectives.length === 0 ? (
          <p style={{ color: "var(--text-muted, #888)", fontSize: "0.875rem" }}>No active objectives for this team.</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
            {objectives.map((obj: unknown) => {
              const o = obj as { objective_id: string; title: string; health_current: string; confidence_current: number; objective_type: string };
              return (
                <a key={o.objective_id} href={`/okrs/${o.objective_id}`} style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", padding: "var(--space-2)", borderRadius: "var(--radius-s)", textDecoration: "none", color: "inherit", background: "var(--surface)" }}>
                  <span style={{ color: HEALTH_COLOR[o.health_current] ?? "#888" }}>●</span>
                  <span style={{ flex: 1, fontSize: "0.875rem" }}>{o.title}</span>
                  <span style={{ fontSize: "0.7rem", background: o.objective_type === "committed" ? "var(--accent)" : "#7c3aed", color: "#fff", borderRadius: "var(--radius-s)", padding: "1px 6px" }}>{o.objective_type}</span>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-muted, #888)" }}>{Math.round((o.confidence_current ?? 0) * 100)}%</span>
                </a>
              );
            })}
          </div>
        )}
      </div>

      {/* Overdue check-ins */}
      <div className="card" style={{ padding: "var(--space-3)" }}>
        <div style={{ fontSize: "0.875rem", fontWeight: 600, marginBottom: "var(--space-2)", color: overdue.length > 0 ? "#ef4444" : "inherit" }}>
          Overdue Check-ins ({overdue.length})
        </div>
        {overdue.length === 0 ? (
          <p style={{ color: "#22c55e", fontSize: "0.875rem" }}>✓ All key results are up to date.</p>
        ) : (
          <table className="data-table" style={{ width: "100%" }}>
            <thead><tr><th>Key Result</th><th>Last Check-in</th><th>Owner</th></tr></thead>
            <tbody>
              {overdue.map((kr: unknown) => {
                const k = kr as { kr_id: string; title: string; last_checkin_at: string | null; owner_user_id: string };
                return (
                  <tr key={k.kr_id}>
                    <td style={{ fontSize: "0.8rem" }}>{k.title}</td>
                    <td style={{ fontSize: "0.8rem", color: "#ef4444" }}>{k.last_checkin_at ?? "Never"}</td>
                    <td style={{ fontSize: "0.8rem" }}>{k.owner_user_id}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export default function TeamDashboardPage() {
  return (
    <PageShell
      title="Team Dashboard"
      subtitle="Team-level objectives, pending check-ins, and required actions"
      breadcrumbs={[{ label: "OKRs", href: "/okrs" }, { label: "Team Dashboard" }]}
    >
      <Suspense fallback={<p>Loading…</p>}>
        <TeamDashboardContent />
      </Suspense>
    </PageShell>
  );
}
