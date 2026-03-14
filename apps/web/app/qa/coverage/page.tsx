"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { PageShell } from "../../../components/page-shell";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface CoverageGap {
  area: string;
  test_count: number;
  severity: string;
  missing_types: string[];
  recommendation: string;
}

interface CoverageReport {
  generated_at: string;
  total_active_tests: number;
  coverage_by_area: Record<string, number>;
  gaps: CoverageGap[];
  unlinked_bugs: string[];
  under_tested_agents: string[];
  recommendations: string[];
  risk_summary: { critical: number; warning: number; info: number };
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: "#dc2626",
  warning: "#b45309",
  info: "#0891b2",
};

const SEVERITY_BG: Record<string, string> = {
  critical: "#fef2f2",
  warning: "#fffbeb",
  info: "#f0f9ff",
};

const SEVERITY_BORDER: Record<string, string> = {
  critical: "#fca5a5",
  warning: "#fcd34d",
  info: "#7dd3fc",
};

const SEVERITY_ICONS: Record<string, string> = {
  critical: "🔴",
  warning: "🟡",
  info: "🔵",
};

function GapCard({ gap }: { gap: CoverageGap }) {
  const color = SEVERITY_COLORS[gap.severity] ?? "var(--muted)";
  const bg = SEVERITY_BG[gap.severity] ?? "var(--surface)";
  const border = SEVERITY_BORDER[gap.severity] ?? "var(--line)";
  const label = gap.area.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <div style={{ background: bg, border: `1px solid ${border}`, borderRadius: 10, padding: "14px 16px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span>{SEVERITY_ICONS[gap.severity]}</span>
          <span style={{ fontWeight: 700, fontSize: "0.9rem", color: "var(--text)" }}>{label}</span>
        </div>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <Link href={`/qa/tests?feature_area=${gap.area}`} style={{ fontSize: "0.72rem", color: color, textDecoration: "underline" }}>
            {gap.test_count} test{gap.test_count !== 1 ? "s" : ""}
          </Link>
          <span style={{ background: `${color}18`, color, border: `1px solid ${color}40`, borderRadius: 5, padding: "1px 7px", fontSize: "0.7rem", fontWeight: 700, textTransform: "uppercase" }}>
            {gap.severity}
          </span>
        </div>
      </div>
      <p style={{ margin: "0 0 8px", fontSize: "0.82rem", color: "#374151", lineHeight: 1.5 }}>{gap.recommendation}</p>
      {gap.missing_types.length > 0 && (
        <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
          <span style={{ fontSize: "0.72rem", color: "var(--muted)" }}>Missing:</span>
          {gap.missing_types.map((t) => (
            <span key={t} style={{ background: `${color}18`, color, border: `1px solid ${color}30`, borderRadius: 5, padding: "1px 6px", fontSize: "0.7rem", fontWeight: 600 }}>
              {t}
            </span>
          ))}
        </div>
      )}
      <div style={{ marginTop: 10 }}>
        <Link href={`/qa/tests/new?feature_area=${gap.area}`} style={{ fontSize: "0.78rem", color, textDecoration: "none", fontWeight: 600 }}>
          + Add test case for {label} →
        </Link>
      </div>
    </div>
  );
}

export default function CoverageGapPage() {
  const [report, setReport] = useState<CoverageReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "critical" | "warning" | "info">("all");

  function load() {
    setLoading(true);
    fetch(`${BACKEND}/qa/coverage?org_id=default`)
      .then((r) => r.ok ? r.json() : null)
      .then(setReport)
      .catch(() => setReport(null))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  const filteredGaps = report?.gaps.filter((g) => filter === "all" || g.severity === filter) ?? [];
  const sortedGaps = [...filteredGaps].sort((a, b) => {
    const order = { critical: 0, warning: 1, info: 2 };
    return (order[a.severity as keyof typeof order] ?? 3) - (order[b.severity as keyof typeof order] ?? 3);
  });

  const headerActions = (
    <button onClick={load} style={{ padding: "7px 14px", borderRadius: 8, border: "1px solid var(--line)", background: "var(--surface)", color: "var(--text)", fontSize: "0.82rem", cursor: "pointer" }}>
      ↻ Re-analyze
    </button>
  );

  return (
    <PageShell
      title="Coverage Gap Analyzer"
      subtitle="Identifies missing, weak, or outdated test coverage across Friday's feature areas"
      breadcrumbs={[{ label: "QA Registry", href: "/qa" }, { label: "Coverage Gaps" }]}
      headerActions={headerActions}
    >
      <div style={{ padding: "20px 28px", maxWidth: 1060 }}>
        {loading ? (
          <div style={{ color: "var(--muted)", padding: "40px 0", textAlign: "center" }}>Analyzing coverage…</div>
        ) : !report ? (
          <div style={{ color: "var(--danger)", padding: "20px 0" }}>Failed to load coverage report.</div>
        ) : (
          <>
            {/* Summary row */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12, marginBottom: 24 }}>
              {[
                { label: "Active Tests", value: report.total_active_tests, color: "var(--accent)" },
                { label: "Critical Gaps", value: report.risk_summary.critical, color: report.risk_summary.critical > 0 ? "#dc2626" : "var(--muted)" },
                { label: "Warnings", value: report.risk_summary.warning, color: report.risk_summary.warning > 0 ? "#b45309" : "var(--muted)" },
                { label: "Info", value: report.risk_summary.info, color: "#0891b2" },
                { label: "Unlinked Bugs", value: report.unlinked_bugs.length, color: report.unlinked_bugs.length > 0 ? "#b45309" : "var(--muted)" },
              ].map(({ label, value, color }) => (
                <div key={label} style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 10, padding: "14px 18px" }}>
                  <div style={{ fontSize: "1.6rem", fontWeight: 700, color, lineHeight: 1 }}>{value}</div>
                  <div style={{ fontSize: "0.72rem", color: "var(--muted)", marginTop: 4, textTransform: "uppercase", letterSpacing: "0.04em" }}>{label}</div>
                </div>
              ))}
            </div>

            {/* Recommendations */}
            {report.recommendations.length > 0 && (
              <div style={{ background: "#f8fafc", border: "1px solid var(--line)", borderRadius: 12, padding: "16px 20px", marginBottom: 24 }}>
                <h3 style={{ margin: "0 0 10px", fontSize: "0.9rem", fontWeight: 700 }}>Recommendations</h3>
                <ul style={{ margin: 0, paddingLeft: 18, display: "flex", flexDirection: "column", gap: 6 }}>
                  {report.recommendations.map((r, i) => (
                    <li key={i} style={{ fontSize: "0.875rem", color: "var(--text)", lineHeight: 1.5 }}>{r}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Coverage by area heatmap */}
            <div style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 12, padding: "16px 20px", marginBottom: 24 }}>
              <h3 style={{ margin: "0 0 12px", fontSize: "0.9rem", fontWeight: 700 }}>Test Count by Feature Area</h3>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(130px, 1fr))", gap: 8 }}>
                {Object.entries(report.coverage_by_area).sort((a, b) => a[0].localeCompare(b[0])).map(([area, count]) => {
                  const intensity = count === 0 ? 0 : count < 3 ? 0.3 : count < 6 ? 0.6 : 1;
                  const bg = count === 0 ? "#fef2f2" : `rgba(15, 92, 192, ${intensity * 0.15 + 0.05})`;
                  const textColor = count === 0 ? "#dc2626" : "var(--text)";
                  return (
                    <Link key={area} href={`/qa/tests?feature_area=${area}`} style={{ textDecoration: "none" }}>
                      <div
                        style={{ background: bg, border: "1px solid var(--line)", borderRadius: 8, padding: "10px 12px", textAlign: "center", cursor: "pointer" }}
                        onMouseOver={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "var(--accent)"; }}
                        onMouseOut={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "var(--line)"; }}
                      >
                        <div style={{ fontSize: "1.25rem", fontWeight: 700, color: textColor }}>{count}</div>
                        <div style={{ fontSize: "0.68rem", color: "var(--muted)", marginTop: 2, textTransform: "capitalize" }}>
                          {area.replace(/_/g, " ")}
                        </div>
                      </div>
                    </Link>
                  );
                })}
              </div>
            </div>

            {/* Gaps section */}
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <h3 style={{ margin: 0, fontSize: "0.9rem", fontWeight: 700 }}>
                  Coverage Gaps ({sortedGaps.length})
                </h3>
                <div style={{ display: "flex", gap: 6 }}>
                  {(["all", "critical", "warning", "info"] as const).map((f) => (
                    <button key={f} onClick={() => setFilter(f)}
                      style={{
                        padding: "4px 12px", borderRadius: 7, border: `1px solid ${filter === f ? "var(--accent)" : "var(--line)"}`,
                        background: filter === f ? "rgba(15,92,192,0.08)" : "transparent",
                        color: filter === f ? "var(--accent)" : "var(--muted)",
                        fontSize: "0.78rem", fontWeight: filter === f ? 700 : 400, cursor: "pointer",
                        textTransform: "capitalize",
                      }}>
                      {f === "all" ? `All (${report.gaps.length})` : `${f} (${report.risk_summary[f as keyof typeof report.risk_summary] ?? 0})`}
                    </button>
                  ))}
                </div>
              </div>

              {sortedGaps.length === 0 ? (
                <div style={{ textAlign: "center", padding: "40px", background: "#f0fdf4", border: "1px solid #86efac", borderRadius: 12 }}>
                  <div style={{ fontSize: "2rem", marginBottom: 8 }}>✓</div>
                  <div style={{ fontWeight: 600, color: "#16a34a" }}>
                    {filter === "all" ? "No coverage gaps detected!" : `No ${filter} gaps`}
                  </div>
                </div>
              ) : (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(400px, 1fr))", gap: 12 }}>
                  {sortedGaps.map((gap) => <GapCard key={gap.area} gap={gap} />)}
                </div>
              )}
            </div>

            {/* Unlinked bugs */}
            {report.unlinked_bugs.length > 0 && (
              <div style={{ background: "#fffbeb", border: "1px solid #fcd34d", borderRadius: 12, padding: "14px 18px", marginTop: 24 }}>
                <div style={{ fontWeight: 700, color: "#b45309", marginBottom: 8 }}>
                  ⚠ {report.unlinked_bugs.length} Bug{report.unlinked_bugs.length > 1 ? "s" : ""} Without Regression Tests
                </div>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {report.unlinked_bugs.map((bugId) => (
                    <span key={bugId} style={{ background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: 5, padding: "2px 8px", fontSize: "0.78rem", color: "#7c3a00" }}>
                      {bugId}
                    </span>
                  ))}
                </div>
                <div style={{ marginTop: 10 }}>
                  <Link href="/qa/tests/new" style={{ fontSize: "0.82rem", color: "#b45309", fontWeight: 600, textDecoration: "none" }}>
                    + Create regression tests for these bugs →
                  </Link>
                </div>
              </div>
            )}

            <div style={{ textAlign: "right", marginTop: 16, fontSize: "0.72rem", color: "var(--muted)" }}>
              Analysis generated: {new Date(report.generated_at).toLocaleString()}
            </div>
          </>
        )}
      </div>
    </PageShell>
  );
}
