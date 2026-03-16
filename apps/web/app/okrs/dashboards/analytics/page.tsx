"use client";

import React, { useEffect, useState } from "react";
import { PageShell } from "@/components/page-shell";

const BACKEND = process.env.NEXT_PUBLIC_FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000";

interface KPI {
  kpi_id: string;
  name: string;
  unit: string;
  current_value: number | null;
  target_band_low: number | null;
  target_band_high: number | null;
  health_status: string;
  update_frequency: string;
  last_updated?: string;
  metric_definition?: string;
}

interface AnalyticsDashboard {
  kpis?: KPI[];
  kr_kpi_coverage_pct?: number;
  manual_kr_count?: number;
  linked_kr_count?: number;
  stale_kr_count?: number;
  missing_baseline_count?: number;
  quality_by_node?: Record<string, number>;
  total_kpis?: number;
}

const HEALTH_COLOR: Record<string, string> = { green: "#16a34a", yellow: "#ca8a04", red: "#dc2626" };
const HEALTH_BG: Record<string, string> = { green: "#f0fdf4", yellow: "#fefce8", red: "#fef2f2" };

export default function AnalyticsDashboard() {
  const [data, setData] = useState<AnalyticsDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  useEffect(() => {
    fetch(`${BACKEND}/okrs/dashboard/analytics?org_id=org-1`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(e => { setError(String(e)); setLoading(false); });
  }, []);

  const kpis = (data?.kpis ?? []).filter(k =>
    !search || k.name.toLowerCase().includes(search.toLowerCase())
  );
  const coveragePct = data?.kr_kpi_coverage_pct ?? 0;
  const qualityNodes = data?.quality_by_node ? Object.entries(data.quality_by_node) : [];

  return (
    <PageShell
      title="Analytics Dashboard"
      subtitle="KPI library, metric coverage, data quality, and OKR scoring analytics"
      breadcrumbs={[{ label: "OKRs", href: "/okrs" }, { label: "Analytics Dashboard" }]}
    >
      {loading && <p style={{ color: "var(--text-muted, #888)" }}>Loading analytics…</p>}
      {error && <p style={{ color: "var(--danger, #dc2626)" }}>{error}</p>}

      {!loading && !error && (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>

          {/* Summary stats */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "var(--space-2)" }}>
            {[
              { label: "Total KPIs", value: data?.total_kpis ?? 0, color: "var(--accent)" },
              { label: "KR-KPI Coverage", value: `${Math.round(coveragePct)}%`, color: coveragePct >= 70 ? "#16a34a" : coveragePct >= 40 ? "#ca8a04" : "#dc2626" },
              { label: "Manual KRs", value: data?.manual_kr_count ?? 0, color: "#6b7280" },
              { label: "Stale KRs", value: data?.stale_kr_count ?? 0, color: (data?.stale_kr_count ?? 0) > 0 ? "#dc2626" : "#6b7280" },
              { label: "Missing Baselines", value: data?.missing_baseline_count ?? 0, color: (data?.missing_baseline_count ?? 0) > 0 ? "#ca8a04" : "#6b7280" },
            ].map(stat => (
              <div key={stat.label} className="card" style={{ padding: "var(--space-2) var(--space-3)" }}>
                <div style={{ fontSize: "1.5rem", fontWeight: 700, color: stat.color }}>{stat.value}</div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-muted, #888)", marginTop: 2 }}>{stat.label}</div>
              </div>
            ))}
          </div>

          {/* Coverage bar */}
          <div className="card" style={{ padding: "var(--space-3)" }}>
            <h3 style={{ margin: "0 0 var(--space-2)", fontSize: "0.875rem", fontWeight: 600 }}>KR Metric Coverage</h3>
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <div style={{ flex: 1, height: 12, background: "var(--border)", borderRadius: 6, overflow: "hidden" }}>
                <div style={{
                  width: `${Math.round(coveragePct)}%`,
                  height: "100%",
                  background: coveragePct >= 70 ? "#16a34a" : coveragePct >= 40 ? "#ca8a04" : "#dc2626",
                  transition: "width 0.4s"
                }} />
              </div>
              <span style={{ fontSize: "0.875rem", fontWeight: 600, minWidth: 40 }}>{Math.round(coveragePct)}%</span>
            </div>
            <p style={{ fontSize: "0.75rem", color: "var(--text-muted, #888)", margin: "var(--space-1) 0 0" }}>
              {data?.linked_kr_count ?? 0} of {(data?.linked_kr_count ?? 0) + (data?.manual_kr_count ?? 0)} key results are linked to a KPI (target: 70%+)
            </p>
          </div>

          {/* Two-column layout */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 280px", gap: "var(--space-3)", alignItems: "start" }}>

            {/* KPI library */}
            <div className="card" style={{ padding: "var(--space-3)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-2)" }}>
                <h3 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 600, flex: 1 }}>KPI Library</h3>
                <input
                  type="text"
                  placeholder="Search KPIs…"
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  className="form-input"
                  style={{ width: 180 }}
                />
              </div>

              {kpis.length === 0 && (
                <p style={{ color: "var(--text-muted, #888)", fontSize: "0.875rem", textAlign: "center", padding: "var(--space-3) 0" }}>
                  No KPIs found. Create KPIs in the <a href="/okrs?tab=kpis" style={{ color: "var(--accent)" }}>OKRs → KPIs</a> tab.
                </p>
              )}

              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
                {kpis.map(kpi => (
                  <div key={kpi.kpi_id} style={{
                    display: "grid",
                    gridTemplateColumns: "1fr auto auto",
                    gap: "var(--space-2)",
                    alignItems: "center",
                    padding: "var(--space-2)",
                    borderRadius: "var(--radius-s)",
                    background: HEALTH_BG[kpi.health_status] ?? "var(--bg)",
                    borderLeft: `3px solid ${HEALTH_COLOR[kpi.health_status] ?? "#6b7280"}`
                  }}>
                    <div>
                      <div style={{ fontSize: "0.875rem", fontWeight: 500 }}>{kpi.name}</div>
                      {kpi.metric_definition && (
                        <div style={{ fontSize: "0.75rem", color: "var(--text-muted, #888)", marginTop: 2 }}>{kpi.metric_definition}</div>
                      )}
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div style={{ fontSize: "1rem", fontWeight: 700, color: HEALTH_COLOR[kpi.health_status] ?? "#6b7280" }}>
                        {kpi.current_value !== null && kpi.current_value !== undefined
                          ? `${kpi.current_value.toLocaleString()}${kpi.unit ? ` ${kpi.unit}` : ""}`
                          : <span style={{ color: "#9ca3af", fontSize: "0.8rem" }}>No data</span>
                        }
                      </div>
                      {(kpi.target_band_low !== null || kpi.target_band_high !== null) && (
                        <div style={{ fontSize: "0.7rem", color: "var(--text-muted, #888)" }}>
                          target: {kpi.target_band_low ?? "—"} – {kpi.target_band_high ?? "—"} {kpi.unit}
                        </div>
                      )}
                    </div>
                    <span style={{
                      fontSize: "0.7rem",
                      background: HEALTH_COLOR[kpi.health_status] ?? "#6b7280",
                      color: "#fff",
                      borderRadius: "var(--radius-s)",
                      padding: "2px 8px",
                      textTransform: "capitalize"
                    }}>
                      {kpi.health_status}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Side: data quality + quality by node */}
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
              <div className="card" style={{ padding: "var(--space-3)" }}>
                <h3 style={{ margin: "0 0 var(--space-2)", fontSize: "0.875rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted, #888)" }}>Data Quality</h3>
                {[
                  { label: "Stale KRs (>14 days)", value: data?.stale_kr_count ?? 0, warn: true },
                  { label: "Missing Baselines", value: data?.missing_baseline_count ?? 0, warn: true },
                  { label: "Manual (no KPI link)", value: data?.manual_kr_count ?? 0, warn: false },
                ].map(item => (
                  <div key={item.label} style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", padding: "var(--space-1) 0", borderBottom: "1px solid var(--border)" }}>
                    <span>{item.label}</span>
                    <span style={{ fontWeight: 600, color: item.warn && item.value > 0 ? "#dc2626" : "inherit" }}>{item.value}</span>
                  </div>
                ))}
              </div>

              {qualityNodes.length > 0 && (
                <div className="card" style={{ padding: "var(--space-3)" }}>
                  <h3 style={{ margin: "0 0 var(--space-2)", fontSize: "0.875rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted, #888)" }}>Quality Score by Team</h3>
                  {qualityNodes.map(([nodeName, score]) => (
                    <div key={nodeName} style={{ marginBottom: "var(--space-1)" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", marginBottom: 3 }}>
                        <span>{nodeName}</span>
                        <span style={{ fontWeight: 600 }}>{score}/10</span>
                      </div>
                      <div style={{ height: 5, background: "var(--border)", borderRadius: 3, overflow: "hidden" }}>
                        <div style={{ width: `${score * 10}%`, height: "100%", background: score >= 7 ? "#16a34a" : score >= 4 ? "#ca8a04" : "#dc2626" }} />
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <div className="card" style={{ padding: "var(--space-3)" }}>
                <h3 style={{ margin: "0 0 var(--space-2)", fontSize: "0.875rem", fontWeight: 600 }}>Quick Links</h3>
                {[
                  { label: "Create KPI", href: "/okrs?tab=kpis" },
                  { label: "View all KRs", href: "/okrs" },
                  { label: "Executive Dashboard", href: "/okrs/dashboards/executive" },
                  { label: "Portfolio Dashboard", href: "/okrs/dashboards/portfolio" },
                ].map(link => (
                  <a key={link.label} href={link.href} style={{ display: "block", fontSize: "0.8rem", color: "var(--accent)", textDecoration: "none", padding: "var(--space-1) 0" }}>
                    → {link.label}
                  </a>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </PageShell>
  );
}
