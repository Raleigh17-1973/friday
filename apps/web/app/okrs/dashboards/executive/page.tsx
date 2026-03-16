"use client";

import { useEffect, useState } from "react";
import { PageShell } from "@/components/page-shell";

const BACKEND = process.env.NEXT_PUBLIC_FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000";
const HEALTH_COLOR: Record<string, string> = { green: "#22c55e", yellow: "#eab308", red: "#ef4444" };

export default function ExecutiveDashboard() {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${BACKEND}/okrs/dashboard/executive?org_id=org-1`)
      .then(r => r.json()).then(setData).catch(() => setData(null)).finally(() => setLoading(false));
  }, []);

  if (loading) return <PageShell title="Executive Dashboard"><p>Loading…</p></PageShell>;
  if (!data) return <PageShell title="Executive Dashboard"><p>Unable to load dashboard data.</p></PageShell>;

  const byHealth = (data.by_health as Record<string, number>) ?? {};
  const atRisk = (data.at_risk_committed as unknown[]) ?? [];
  const totalObj = (data.total_objectives as number) ?? 0;
  const avgConf = (data.avg_confidence as number) ?? 0;

  return (
    <PageShell
      title="Executive Dashboard"
      subtitle="Company-wide OKR health, at-risk objectives, and portfolio confidence"
      breadcrumbs={[{ label: "OKRs", href: "/okrs" }, { label: "Executive Dashboard" }]}
    >
      {/* Health tiles */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "var(--space-2)", marginBottom: "var(--space-3)" }}>
        {[
          { label: "Total Objectives", value: totalObj, color: "var(--accent)" },
          { label: "On Track", value: byHealth.green ?? 0, color: "#22c55e" },
          { label: "At Risk", value: byHealth.yellow ?? 0, color: "#eab308" },
          { label: "Off Track", value: byHealth.red ?? 0, color: "#ef4444" },
        ].map(tile => (
          <div key={tile.label} className="card" style={{ padding: "var(--space-3)", textAlign: "center" }}>
            <div style={{ fontSize: "2rem", fontWeight: 700, color: tile.color }}>{tile.value}</div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted, #888)", marginTop: 4 }}>{tile.label}</div>
          </div>
        ))}
      </div>

      {/* Avg confidence */}
      <div className="card" style={{ padding: "var(--space-3)", marginBottom: "var(--space-3)" }}>
        <div style={{ fontSize: "0.875rem", fontWeight: 600, marginBottom: "var(--space-1)" }}>Portfolio Confidence</div>
        <div style={{ height: 10, background: "var(--border)", borderRadius: 5, overflow: "hidden" }}>
          <div style={{ height: "100%", width: `${Math.round(avgConf * 100)}%`, background: avgConf >= 0.75 ? "#22c55e" : avgConf >= 0.5 ? "#eab308" : "#ef4444", borderRadius: 5, transition: "width 0.4s" }} />
        </div>
        <div style={{ fontSize: "0.75rem", color: "var(--text-muted, #888)", marginTop: 4 }}>{Math.round(avgConf * 100)}% average confidence across all active objectives</div>
      </div>

      {/* At-risk committed */}
      <div className="card" style={{ padding: "var(--space-3)", marginBottom: "var(--space-3)" }}>
        <div style={{ fontSize: "0.875rem", fontWeight: 600, marginBottom: "var(--space-2)" }}>
          At-Risk Committed Objectives ({atRisk.length})
        </div>
        {atRisk.length === 0 ? (
          <p style={{ color: "#22c55e", fontSize: "0.875rem" }}>✓ No committed objectives are currently at risk.</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
            {atRisk.map((obj: unknown) => {
              const o = obj as { objective_id: string; title: string; health_current: string; confidence_current: number };
              return (
                <a key={o.objective_id} href={`/okrs/${o.objective_id}`} style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", padding: "var(--space-2)", background: "rgba(239,68,68,0.08)", borderRadius: "var(--radius-s)", textDecoration: "none", color: "inherit" }}>
                  <span style={{ color: HEALTH_COLOR[o.health_current] ?? "#888", fontSize: "1.1rem" }}>●</span>
                  <span style={{ flex: 1, fontSize: "0.875rem" }}>{o.title}</span>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-muted, #888)" }}>{Math.round((o.confidence_current ?? 0) * 100)}% confidence</span>
                </a>
              );
            })}
          </div>
        )}
      </div>

      {/* Bottleneck dependencies */}
      {Array.isArray(data.bottleneck_dependencies) && (data.bottleneck_dependencies as unknown[]).length > 0 && (
        <div className="card" style={{ padding: "var(--space-3)" }}>
          <div style={{ fontSize: "0.875rem", fontWeight: 600, marginBottom: "var(--space-2)" }}>Bottleneck Dependencies</div>
          <table className="data-table" style={{ width: "100%" }}>
            <thead><tr><th>Objective</th><th>Blocked-by Count</th></tr></thead>
            <tbody>
              {(data.bottleneck_dependencies as unknown[]).map((b: unknown) => {
                const bd = b as { objective_id: string; title: string; blocked_by_count: number };
                return (
                  <tr key={bd.objective_id}>
                    <td><a href={`/okrs/${bd.objective_id}`} style={{ color: "var(--accent)" }}>{bd.title}</a></td>
                    <td style={{ color: "#ef4444", fontWeight: 600 }}>{bd.blocked_by_count}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </PageShell>
  );
}
