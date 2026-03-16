"use client";

import React, { useEffect, useState } from "react";
import { PageShell } from "@/components/page-shell";

const BACKEND = process.env.NEXT_PUBLIC_FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000";

interface PortfolioObjective {
  objective_id: string;
  title: string;
  objective_type: string;
  health_current: string;
  confidence_current: number;
  score?: number;
  kr_count?: number;
  node_name?: string;
  owner_user_id?: string;
}

interface PortfolioDashboard {
  period_id?: string;
  objectives_by_node?: Record<string, PortfolioObjective[]>;
  total_objectives?: number;
  at_risk_committed?: number;
  avg_score?: number;
  overloaded_teams?: string[];
  shared_commitments?: Array<{ title: string; teams: string[] }>;
  bottleneck_krs?: Array<{ kr_id: string; title: string; score: number; node_name: string }>;
}

const HEALTH_COLOR: Record<string, string> = { green: "#16a34a", yellow: "#ca8a04", red: "#dc2626" };

function ScoreBar({ value, health }: { value: number; health: string }) {
  const color = HEALTH_COLOR[health] ?? "#6b7280";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-1)", flex: 1 }}>
      <div style={{ flex: 1, height: 6, background: "var(--border)", borderRadius: 3, overflow: "hidden" }}>
        <div style={{ width: `${Math.round(value * 100)}%`, height: "100%", background: color, transition: "width 0.3s" }} />
      </div>
      <span style={{ fontSize: "0.75rem", color, minWidth: 32, textAlign: "right" }}>{Math.round(value * 100)}%</span>
    </div>
  );
}

export default function PortfolioDashboard() {
  const [data, setData] = useState<PortfolioDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [periodId, setPeriodId] = useState("");
  const [periods, setPeriods] = useState<Array<{ period_id: string; name: string }>>([]);

  useEffect(() => {
    fetch(`${BACKEND}/okrs/periods?org_id=org-1`)
      .then(r => r.json())
      .then(d => {
        const ps = d.periods ?? d ?? [];
        setPeriods(ps);
        const active = ps.find((p: { status: string }) => p.status === "active");
        if (active) setPeriodId(active.period_id);
        else if (ps.length > 0) setPeriodId(ps[0].period_id);
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!periodId) return;
    setLoading(true);
    const nodeParam = "";
    fetch(`${BACKEND}/okrs/dashboard/portfolio?org_node_id=node-company&period_id=${periodId}&org_id=org-1`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(e => { setError(String(e)); setLoading(false); });
  }, [periodId]);

  const nodes = data?.objectives_by_node ? Object.entries(data.objectives_by_node) : [];
  const sharedCommitments = data?.shared_commitments ?? [];
  const overloaded = data?.overloaded_teams ?? [];
  const bottlenecks = data?.bottleneck_krs ?? [];

  return (
    <PageShell
      title="Portfolio Dashboard"
      subtitle="Objectives grouped by org node with KR trends and blocker analysis"
      breadcrumbs={[{ label: "OKRs", href: "/okrs" }, { label: "Portfolio Dashboard" }]}
    >
      {/* Period selector */}
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-3)" }}>
        <label style={{ fontSize: "0.875rem", color: "var(--text-muted, #888)" }}>Period</label>
        <select
          value={periodId}
          onChange={e => setPeriodId(e.target.value)}
          className="form-input"
          style={{ width: 200 }}
        >
          {periods.map(p => <option key={p.period_id} value={p.period_id}>{p.name}</option>)}
        </select>
        {overloaded.length > 0 && (
          <span style={{ marginLeft: "auto", fontSize: "0.8rem", background: "#fef3c7", color: "#92400e", padding: "2px 10px", borderRadius: "var(--radius-s)" }}>
            ⚠ {overloaded.length} team{overloaded.length !== 1 ? "s" : ""} overloaded (&gt;4 objectives)
          </span>
        )}
      </div>

      {loading && <p style={{ color: "var(--text-muted, #888)" }}>Loading portfolio data…</p>}
      {error && <p style={{ color: "var(--danger, #dc2626)" }}>{error}</p>}

      {!loading && !error && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: "var(--space-3)", alignItems: "start" }}>
          {/* Main — objectives by org node */}
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            {nodes.length === 0 && (
              <div className="card" style={{ padding: "var(--space-3)", color: "var(--text-muted, #888)", textAlign: "center" }}>
                No objectives found for this period.
              </div>
            )}
            {nodes.map(([nodeName, objectives]) => (
              <div key={nodeName} className="card" style={{ padding: "var(--space-3)" }}>
                <h3 style={{ margin: "0 0 var(--space-2)", fontSize: "0.95rem", fontWeight: 600 }}>{nodeName}</h3>
                <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
                  {(objectives as PortfolioObjective[]).map(obj => (
                    <div key={obj.objective_id} style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", padding: "var(--space-2)", background: "var(--bg)", borderRadius: "var(--radius-s)" }}>
                      <span style={{ color: HEALTH_COLOR[obj.health_current] ?? "#888", fontSize: "1.1rem" }}>●</span>
                      <a href={`/okrs/${obj.objective_id}`} style={{ flex: 1, textDecoration: "none", color: "inherit", fontSize: "0.875rem", fontWeight: 500 }}>
                        {obj.title}
                      </a>
                      <span style={{ fontSize: "0.7rem", background: obj.objective_type === "committed" ? "var(--accent)" : "#7c3aed", color: "#fff", borderRadius: "var(--radius-s)", padding: "1px 6px" }}>
                        {obj.objective_type}
                      </span>
                      <ScoreBar value={obj.score ?? 0} health={obj.health_current} />
                      <span style={{ fontSize: "0.75rem", color: "var(--text-muted, #888)", minWidth: 56, textAlign: "right" }}>
                        {obj.kr_count ?? 0} KRs
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* Side panels */}
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>

            {/* Stats */}
            <div className="card" style={{ padding: "var(--space-3)" }}>
              <h3 style={{ margin: "0 0 var(--space-2)", fontSize: "0.875rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted, #888)" }}>Portfolio Health</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.875rem" }}>
                  <span>Total Objectives</span>
                  <strong>{data?.total_objectives ?? 0}</strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.875rem" }}>
                  <span style={{ color: "#dc2626" }}>At-Risk Committed</span>
                  <strong style={{ color: "#dc2626" }}>{data?.at_risk_committed ?? 0}</strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.875rem" }}>
                  <span>Avg Score</span>
                  <strong>{Math.round((data?.avg_score ?? 0) * 100)}%</strong>
                </div>
              </div>
            </div>

            {/* Shared commitments */}
            {sharedCommitments.length > 0 && (
              <div className="card" style={{ padding: "var(--space-3)" }}>
                <h3 style={{ margin: "0 0 var(--space-2)", fontSize: "0.875rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted, #888)" }}>Shared Commitments</h3>
                {sharedCommitments.map((sc, i) => (
                  <div key={i} style={{ marginBottom: "var(--space-2)", fontSize: "0.8rem" }}>
                    <div style={{ fontWeight: 500 }}>{sc.title}</div>
                    <div style={{ color: "var(--text-muted, #888)" }}>{sc.teams.join(" · ")}</div>
                  </div>
                ))}
              </div>
            )}

            {/* Bottleneck KRs */}
            {bottlenecks.length > 0 && (
              <div className="card" style={{ padding: "var(--space-3)" }}>
                <h3 style={{ margin: "0 0 var(--space-2)", fontSize: "0.875rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "#dc2626" }}>Bottleneck Key Results</h3>
                {bottlenecks.map(kr => (
                  <div key={kr.kr_id} style={{ marginBottom: "var(--space-2)", fontSize: "0.8rem" }}>
                    <div style={{ fontWeight: 500 }}>{kr.title}</div>
                    <div style={{ display: "flex", justifyContent: "space-between", color: "var(--text-muted, #888)" }}>
                      <span>{kr.node_name}</span>
                      <span style={{ color: kr.score < 0.3 ? "#dc2626" : "#ca8a04" }}>{Math.round(kr.score * 100)}%</span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Overloaded teams */}
            {overloaded.length > 0 && (
              <div className="card" style={{ padding: "var(--space-3)", borderLeft: "3px solid #f59e0b" }}>
                <h3 style={{ margin: "0 0 var(--space-2)", fontSize: "0.875rem", fontWeight: 600, color: "#92400e" }}>Overloaded Teams</h3>
                {overloaded.map((t, i) => (
                  <div key={i} style={{ fontSize: "0.8rem", padding: "var(--space-1) 0", color: "#92400e" }}>⚠ {t}</div>
                ))}
                <p style={{ fontSize: "0.75rem", color: "var(--text-muted, #888)", marginTop: "var(--space-1)" }}>
                  Teams with more than 4 active objectives — consider reducing scope.
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </PageShell>
  );
}
