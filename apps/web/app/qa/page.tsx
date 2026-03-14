"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { PageShell } from "../../components/page-shell";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface QASummary {
  total: number;
  active: number;
  draft: number;
  deprecated: number;
  by_type: Record<string, number>;
  by_area: Record<string, number>;
  release_blockers: number;
  suite_count: number;
  run_count: number;
  open_bugs: number;
  coverage_areas: number;
  recent_tests: {
    tc_id: string;
    title: string;
    feature_area: string;
    test_type: string;
    status: string;
    created_at: string;
  }[];
}

const TYPE_COLORS: Record<string, string> = {
  smoke: "#16a34a",
  regression: "#0f5cc0",
  deep: "#7c3aed",
  edge: "#b45309",
  ux: "#0891b2",
  safety: "#dc2626",
  data_integrity: "#9333ea",
  orchestration: "#059669",
  document_quality: "#d97706",
};

const TYPE_LABELS: Record<string, string> = {
  smoke: "Smoke",
  regression: "Regression",
  deep: "Deep",
  edge: "Edge",
  ux: "UX",
  safety: "Safety",
  data_integrity: "Data Integrity",
  orchestration: "Orchestration",
  document_quality: "Doc Quality",
};

function StatCard({
  label,
  value,
  sub,
  accent,
  href,
}: {
  label: string;
  value: number | string;
  sub?: string;
  accent?: string;
  href?: string;
}) {
  const content = (
    <div
      style={{
        background: "var(--surface)",
        border: "1px solid var(--line)",
        borderRadius: 12,
        padding: "18px 22px",
        display: "flex",
        flexDirection: "column",
        gap: 4,
        cursor: href ? "pointer" : "default",
        transition: "box-shadow 0.15s",
      }}
      onMouseOver={(e) => { if (href) (e.currentTarget as HTMLElement).style.boxShadow = "0 2px 8px rgba(0,0,0,0.08)"; }}
      onMouseOut={(e) => { (e.currentTarget as HTMLElement).style.boxShadow = "none"; }}
    >
      <span style={{ fontSize: "1.75rem", fontWeight: 700, color: accent ?? "var(--text)", lineHeight: 1 }}>
        {value}
      </span>
      <span style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
        {label}
      </span>
      {sub && <span style={{ fontSize: "0.72rem", color: "var(--muted)" }}>{sub}</span>}
    </div>
  );
  return href ? <Link href={href} style={{ textDecoration: "none" }}>{content}</Link> : content;
}

function TypeBar({ label, count, total, color }: { label: string; count: number; total: number; color: string }) {
  const pct = total > 0 ? Math.round((count / total) * 100) : 0;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "5px 0" }}>
      <span style={{
        width: 80, flexShrink: 0, fontSize: "0.78rem", color: "var(--text)",
        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
      }}>{label}</span>
      <div style={{ flex: 1, height: 8, background: "var(--surface-2)", borderRadius: 4, overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 4, transition: "width 0.4s ease" }} />
      </div>
      <span style={{ width: 36, flexShrink: 0, textAlign: "right", fontSize: "0.78rem", fontWeight: 600, color: "var(--muted)" }}>
        {count}
      </span>
    </div>
  );
}

function AreaRow({ area, count }: { area: string; count: number }) {
  const label = area.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  const hasSmoke = count > 0;
  return (
    <Link
      href={`/qa/tests?feature_area=${area}`}
      style={{ textDecoration: "none" }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "9px 14px",
          borderBottom: "1px solid var(--line)",
          cursor: "pointer",
        }}
        onMouseOver={(e) => { (e.currentTarget as HTMLElement).style.background = "var(--surface-2)"; }}
        onMouseOut={(e) => { (e.currentTarget as HTMLElement).style.background = "transparent"; }}
      >
        <span style={{
          width: 8, height: 8, borderRadius: "50%", flexShrink: 0,
          background: count === 0 ? "var(--danger)" : count < 3 ? "var(--warning)" : "var(--success)",
        }} />
        <span style={{ flex: 1, fontSize: "0.875rem", color: "var(--text)" }}>{label}</span>
        <span style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--muted)" }}>{count} tests</span>
        <span style={{ fontSize: "0.72rem", color: count === 0 ? "var(--danger)" : count < 3 ? "var(--warning)" : "var(--success)" }}>
          {count === 0 ? "No coverage" : count < 3 ? "Minimal" : "Covered"}
        </span>
        <span style={{ color: "var(--muted)", fontSize: "0.8rem" }}>›</span>
      </div>
    </Link>
  );
}

function TestTypePill({ type }: { type: string }) {
  const color = TYPE_COLORS[type] ?? "var(--muted)";
  return (
    <span style={{
      background: `${color}18`,
      color,
      border: `1px solid ${color}40`,
      borderRadius: 6,
      padding: "1px 7px",
      fontSize: "0.7rem",
      fontWeight: 600,
      letterSpacing: "0.03em",
    }}>
      {TYPE_LABELS[type] ?? type}
    </span>
  );
}

export default function QAHomePage() {
  const [summary, setSummary] = useState<QASummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${BACKEND}/qa/summary?org_id=default`)
      .then((r) => r.ok ? r.json() : null)
      .then((d) => setSummary(d))
      .catch(() => setSummary(null))
      .finally(() => setLoading(false));
  }, []);

  const totalByType = summary ? Object.values(summary.by_type).reduce((a, b) => a + b, 0) : 0;

  const ALL_AREAS = [
    "chat", "agent_orchestration", "documents", "okrs", "workspaces",
    "navigation", "approvals", "ui_consistency", "provenance",
    "permissions", "memory", "analytics", "processes",
  ];

  const headerActions = (
    <div style={{ display: "flex", gap: 8 }}>
      <Link href="/qa/coverage">
        <button style={{
          padding: "7px 16px", borderRadius: 8, border: "1px solid var(--line)",
          background: "var(--surface)", color: "var(--text)", fontSize: "0.85rem",
          cursor: "pointer", fontWeight: 500,
        }}>
          Coverage Gaps
        </button>
      </Link>
      <Link href="/qa/tests/new">
        <button style={{
          padding: "7px 16px", borderRadius: 8, border: "none",
          background: "var(--accent)", color: "#fff", fontSize: "0.85rem",
          cursor: "pointer", fontWeight: 600,
        }}>
          + New Test Case
        </button>
      </Link>
    </div>
  );

  return (
    <PageShell
      title="QA Registry"
      subtitle="Test case management, coverage tracking, and QA intelligence"
      headerActions={headerActions}
    >
      <div style={{ padding: "24px 28px", maxWidth: 1100 }}>
        {loading ? (
          <div style={{ color: "var(--muted)", padding: "40px 0", textAlign: "center" }}>
            Loading QA registry…
          </div>
        ) : !summary ? (
          <div style={{ color: "var(--danger)", padding: "20px 0" }}>Failed to load QA summary.</div>
        ) : (
          <>
            {/* ── Stat Cards ─────────────────────────────────────────── */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12, marginBottom: 28 }}>
              <StatCard label="Total Tests" value={summary.total} href="/qa/tests" />
              <StatCard label="Active" value={summary.active} accent="var(--success)" href="/qa/tests?status=active" />
              <StatCard label="Draft" value={summary.draft} accent="var(--warning)" href="/qa/tests?status=draft" />
              <StatCard label="Release Blockers" value={summary.release_blockers} accent={summary.release_blockers > 0 ? "var(--danger)" : "var(--muted)"} href="/qa/tests?release_blocker=true" />
              <StatCard label="Suites" value={summary.suite_count} href="/qa/suites" />
              <StatCard label="Runs" value={summary.run_count} href="/qa/runs" />
              <StatCard label="Open Bugs" value={summary.open_bugs} accent={summary.open_bugs > 0 ? "var(--warning)" : "var(--muted)"} />
              <StatCard label="Coverage Areas" value={summary.coverage_areas} sub={`of 13 feature areas`} />
            </div>

            {/* ── Two-column layout ──────────────────────────────────── */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 24 }}>

              {/* Test Type Distribution */}
              <div style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 12, padding: "18px 20px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
                  <h3 style={{ margin: 0, fontSize: "0.9rem", fontWeight: 700 }}>Test Type Distribution</h3>
                  <span style={{ fontSize: "0.72rem", color: "var(--muted)" }}>{totalByType} active tests</span>
                </div>
                {Object.entries(TYPE_LABELS).map(([type, label]) => (
                  <TypeBar
                    key={type}
                    label={label}
                    count={summary.by_type[type] ?? 0}
                    total={totalByType}
                    color={TYPE_COLORS[type] ?? "var(--muted)"}
                  />
                ))}
              </div>

              {/* Quick Actions */}
              <div style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 12, padding: "18px 20px" }}>
                <h3 style={{ margin: "0 0 14px", fontSize: "0.9rem", fontWeight: 700 }}>Quick Actions</h3>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {[
                    { label: "View all test cases", href: "/qa/tests", desc: "Browse, search, and filter the registry" },
                    { label: "Create a new suite", href: "/qa/suites", desc: "Assemble tests into a runnable suite" },
                    { label: "Start a test run", href: "/qa/runs", desc: "Execute a suite and record results" },
                    { label: "Analyze coverage gaps", href: "/qa/coverage", desc: "Identify weak or missing test coverage" },
                    { label: "View bug reports", href: "/qa/bugs", desc: "Open bugs and regression tracking" },
                  ].map((a) => (
                    <Link key={a.href} href={a.href} style={{ textDecoration: "none" }}>
                      <div
                        style={{
                          display: "flex", justifyContent: "space-between", alignItems: "center",
                          padding: "8px 12px", borderRadius: 8, border: "1px solid var(--line)",
                          cursor: "pointer",
                        }}
                        onMouseOver={(e) => { (e.currentTarget as HTMLElement).style.background = "var(--surface-2)"; }}
                        onMouseOut={(e) => { (e.currentTarget as HTMLElement).style.background = "transparent"; }}
                      >
                        <div>
                          <div style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--accent)" }}>{a.label}</div>
                          <div style={{ fontSize: "0.72rem", color: "var(--muted)" }}>{a.desc}</div>
                        </div>
                        <span style={{ color: "var(--muted)", fontSize: "1rem" }}>›</span>
                      </div>
                    </Link>
                  ))}
                </div>
              </div>
            </div>

            {/* ── Feature Area Coverage ──────────────────────────────── */}
            <div style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 12, marginBottom: 24 }}>
              <div style={{
                display: "flex", justifyContent: "space-between", alignItems: "center",
                padding: "14px 18px", borderBottom: "1px solid var(--line)",
              }}>
                <h3 style={{ margin: 0, fontSize: "0.9rem", fontWeight: 700 }}>Feature Area Coverage</h3>
                <Link href="/qa/coverage" style={{ fontSize: "0.78rem", color: "var(--accent)", textDecoration: "none" }}>
                  Full gap analysis →
                </Link>
              </div>
              {ALL_AREAS.map((area) => (
                <AreaRow key={area} area={area} count={summary.by_area[area] ?? 0} />
              ))}
            </div>

            {/* ── Recently Added Tests ────────────────────────────────── */}
            {summary.recent_tests.length > 0 && (
              <div style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 12 }}>
                <div style={{
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                  padding: "14px 18px", borderBottom: "1px solid var(--line)",
                }}>
                  <h3 style={{ margin: 0, fontSize: "0.9rem", fontWeight: 700 }}>Recently Added</h3>
                  <Link href="/qa/tests" style={{ fontSize: "0.78rem", color: "var(--accent)", textDecoration: "none" }}>
                    All tests →
                  </Link>
                </div>
                {summary.recent_tests.map((t) => (
                  <Link key={t.tc_id} href={`/qa/tests/${t.tc_id}`} style={{ textDecoration: "none" }}>
                    <div
                      style={{
                        display: "flex", alignItems: "center", gap: 12,
                        padding: "10px 18px", borderBottom: "1px solid var(--line)",
                      }}
                      onMouseOver={(e) => { (e.currentTarget as HTMLElement).style.background = "var(--surface-2)"; }}
                      onMouseOut={(e) => { (e.currentTarget as HTMLElement).style.background = "transparent"; }}
                    >
                      <TestTypePill type={t.test_type} />
                      <span style={{ flex: 1, fontSize: "0.875rem", fontWeight: 500, color: "var(--text)" }}>{t.title}</span>
                      <span style={{ fontSize: "0.75rem", color: "var(--muted)", textTransform: "capitalize" }}>
                        {t.feature_area.replace(/_/g, " ")}
                      </span>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </PageShell>
  );
}
