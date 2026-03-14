"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { PageShell } from "../../../components/page-shell";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface TestCase {
  tc_id: string;
  title: string;
  feature_area: string;
  subfeature: string;
  test_type: string;
  priority: string;
  severity_if_fails: string;
  status: string;
  release_blocker: boolean;
  created_at: string;
  updated_at: string;
  tags: string[];
  applies_to_agents: string[];
}

const FEATURE_AREAS = [
  "chat", "agent_orchestration", "documents", "okrs", "workspaces",
  "navigation", "approvals", "ui_consistency", "provenance",
  "permissions", "memory", "analytics", "processes",
];

const TEST_TYPES = [
  "smoke", "regression", "deep", "edge", "ux",
  "safety", "data_integrity", "orchestration", "document_quality",
];

const PRIORITIES = ["critical", "high", "medium", "low"];

const TYPE_COLORS: Record<string, string> = {
  smoke: "#16a34a", regression: "#0f5cc0", deep: "#7c3aed",
  edge: "#b45309", ux: "#0891b2", safety: "#dc2626",
  data_integrity: "#9333ea", orchestration: "#059669", document_quality: "#d97706",
};

const PRIORITY_COLORS: Record<string, string> = {
  critical: "#dc2626", high: "#b45309", medium: "#0f5cc0", low: "#4e657a",
};

const STATUS_COLORS: Record<string, string> = {
  active: "#16a34a", draft: "#b45309", deprecated: "#9ca3af",
};

function Pill({ label, color }: { label: string; color: string }) {
  return (
    <span style={{
      background: `${color}18`, color, border: `1px solid ${color}40`,
      borderRadius: 6, padding: "1px 7px", fontSize: "0.7rem", fontWeight: 600,
      whiteSpace: "nowrap",
    }}>
      {label}
    </span>
  );
}

function Select({
  value, onChange, options, placeholder,
}: {
  value: string; onChange: (v: string) => void;
  options: string[]; placeholder: string;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={{
        padding: "6px 10px", borderRadius: 8, border: "1px solid var(--line)",
        background: "var(--surface)", color: value ? "var(--text)" : "var(--muted)",
        fontSize: "0.82rem", cursor: "pointer",
      }}
    >
      <option value="">{placeholder}</option>
      {options.map((o) => (
        <option key={o} value={o}>{o.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}</option>
      ))}
    </select>
  );
}

export default function TestCaseListPage() {
  const searchParams = useSearchParams();
  const [tests, setTests] = useState<TestCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [featureArea, setFeatureArea] = useState(searchParams.get("feature_area") ?? "");
  const [testType, setTestType] = useState(searchParams.get("test_type") ?? "");
  const [status, setStatus] = useState(searchParams.get("status") ?? "");
  const [priority, setPriority] = useState("");
  const [releaseBlocker, setReleaseBlocker] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams({ org_id: "default" });
    if (featureArea) params.set("feature_area", featureArea);
    if (testType) params.set("test_type", testType);
    if (status) params.set("status", status);
    if (priority) params.set("priority", priority);
    if (releaseBlocker) params.set("release_blocker", "true");
    if (search) params.set("search", search);
    fetch(`${BACKEND}/qa/tests?${params}`)
      .then((r) => r.ok ? r.json() : [])
      .then(setTests)
      .catch(() => setTests([]))
      .finally(() => setLoading(false));
  }, [featureArea, testType, status, priority, releaseBlocker, search]);

  useEffect(() => { load(); }, [load]);

  const clearFilters = () => {
    setFeatureArea(""); setTestType(""); setStatus(""); setPriority("");
    setReleaseBlocker(false); setSearch("");
  };

  const hasFilters = featureArea || testType || status || priority || releaseBlocker || search;

  const headerActions = (
    <Link href="/qa/tests/new">
      <button style={{
        padding: "7px 16px", borderRadius: 8, border: "none",
        background: "var(--accent)", color: "#fff", fontSize: "0.85rem",
        cursor: "pointer", fontWeight: 600,
      }}>
        + New Test Case
      </button>
    </Link>
  );

  return (
    <PageShell
      title="Test Cases"
      subtitle="All registered test cases"
      breadcrumbs={[{ label: "QA Registry", href: "/qa" }, { label: "Test Cases" }]}
      headerActions={headerActions}
    >
      <div style={{ padding: "20px 28px" }}>
        {/* Filters */}
        <div style={{
          display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center",
          marginBottom: 16, padding: "12px 16px",
          background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 10,
        }}>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search titles, descriptions, tags…"
            style={{
              padding: "6px 10px", borderRadius: 8, border: "1px solid var(--line)",
              background: "var(--surface-2)", color: "var(--text)", fontSize: "0.82rem",
              width: 240,
            }}
            onKeyDown={(e) => e.key === "Enter" && load()}
          />
          <Select value={featureArea} onChange={setFeatureArea} options={FEATURE_AREAS} placeholder="All Areas" />
          <Select value={testType} onChange={setTestType} options={TEST_TYPES} placeholder="All Types" />
          <Select value={status} onChange={setStatus} options={["active", "draft", "deprecated"]} placeholder="All Statuses" />
          <Select value={priority} onChange={setPriority} options={PRIORITIES} placeholder="All Priorities" />
          <label style={{ display: "flex", alignItems: "center", gap: 5, fontSize: "0.82rem", color: "var(--text)", cursor: "pointer" }}>
            <input type="checkbox" checked={releaseBlocker} onChange={(e) => setReleaseBlocker(e.target.checked)} />
            Release blockers only
          </label>
          {hasFilters && (
            <button
              onClick={clearFilters}
              style={{ padding: "5px 10px", borderRadius: 7, border: "1px solid var(--line)", background: "transparent", color: "var(--muted)", fontSize: "0.78rem", cursor: "pointer" }}
            >
              Clear filters
            </button>
          )}
          <span style={{ marginLeft: "auto", fontSize: "0.78rem", color: "var(--muted)" }}>
            {loading ? "Loading…" : `${tests.length} test${tests.length !== 1 ? "s" : ""}`}
          </span>
        </div>

        {/* Table */}
        <div style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 12, overflow: "hidden" }}>
          {/* Header */}
          <div style={{
            display: "grid",
            gridTemplateColumns: "1fr 120px 100px 80px 80px 60px",
            padding: "8px 16px",
            background: "var(--surface-2)",
            borderBottom: "1px solid var(--line)",
            fontSize: "0.72rem", fontWeight: 700,
            color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em",
          }}>
            <span>Test Case</span>
            <span>Type</span>
            <span>Area</span>
            <span>Priority</span>
            <span>Status</span>
            <span style={{ textAlign: "center" }}>Blocker</span>
          </div>

          {loading ? (
            <div style={{ padding: "40px", textAlign: "center", color: "var(--muted)" }}>Loading…</div>
          ) : tests.length === 0 ? (
            <div style={{ padding: "40px", textAlign: "center" }}>
              <div style={{ fontSize: "2rem", marginBottom: 8 }}>🔍</div>
              <div style={{ fontWeight: 600, color: "var(--text)", marginBottom: 4 }}>No test cases found</div>
              <div style={{ fontSize: "0.85rem", color: "var(--muted)", marginBottom: 16 }}>
                {hasFilters ? "Try clearing your filters" : "Add your first test case to get started"}
              </div>
              {!hasFilters && (
                <Link href="/qa/tests/new">
                  <button style={{ padding: "8px 18px", borderRadius: 8, border: "none", background: "var(--accent)", color: "#fff", fontSize: "0.85rem", cursor: "pointer" }}>
                    + New Test Case
                  </button>
                </Link>
              )}
            </div>
          ) : (
            tests.map((tc) => (
              <Link key={tc.tc_id} href={`/qa/tests/${tc.tc_id}`} style={{ textDecoration: "none" }}>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 120px 100px 80px 80px 60px",
                    padding: "11px 16px",
                    borderBottom: "1px solid var(--line)",
                    alignItems: "center",
                    gap: 0,
                  }}
                  onMouseOver={(e) => { (e.currentTarget as HTMLElement).style.background = "var(--surface-2)"; }}
                  onMouseOut={(e) => { (e.currentTarget as HTMLElement).style.background = "transparent"; }}
                >
                  <div style={{ minWidth: 0 }}>
                    <div style={{
                      fontWeight: 600, fontSize: "0.875rem", color: "var(--text)",
                      overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                    }}>
                      {tc.title}
                    </div>
                    {tc.subfeature && (
                      <div style={{ fontSize: "0.72rem", color: "var(--muted)", marginTop: 1 }}>{tc.subfeature}</div>
                    )}
                  </div>
                  <div>
                    <Pill label={tc.test_type.replace(/_/g, " ")} color={TYPE_COLORS[tc.test_type] ?? "var(--muted)"} />
                  </div>
                  <div style={{ fontSize: "0.78rem", color: "var(--muted)", textTransform: "capitalize" }}>
                    {tc.feature_area.replace(/_/g, " ")}
                  </div>
                  <div>
                    <Pill label={tc.priority} color={PRIORITY_COLORS[tc.priority] ?? "var(--muted)"} />
                  </div>
                  <div>
                    <Pill label={tc.status} color={STATUS_COLORS[tc.status] ?? "var(--muted)"} />
                  </div>
                  <div style={{ textAlign: "center", fontSize: "0.85rem" }}>
                    {tc.release_blocker ? "🔴" : ""}
                  </div>
                </div>
              </Link>
            ))
          )}
        </div>
      </div>
    </PageShell>
  );
}
