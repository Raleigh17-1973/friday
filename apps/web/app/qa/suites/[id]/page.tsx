"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { PageShell } from "../../../../components/page-shell";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface TestCase {
  tc_id: string;
  title: string;
  feature_area: string;
  test_type: string;
  priority: string;
  status: string;
  release_blocker: boolean;
}

interface Suite {
  suite_id: string;
  name: string;
  description: string;
  suite_type: string;
  feature_areas: string[];
  test_case_ids: string[];
  generated_by_rule: string;
  owner: string;
  created_at: string;
  updated_at: string;
  status: string;
  test_cases: TestCase[];
}

interface Run {
  run_id: string;
  title: string;
  environment: string;
  started_at: string;
  completed_at: string | null;
  status: string;
  pass_count: number;
  fail_count: number;
  blocked_count: number;
  not_run_count: number;
}

const TYPE_COLORS: Record<string, string> = {
  smoke: "#16a34a", regression: "#0f5cc0", deep: "#7c3aed", edge: "#b45309",
  ux: "#0891b2", safety: "#dc2626", data_integrity: "#9333ea",
  orchestration: "#059669", document_quality: "#d97706",
};
const PRIORITY_COLORS: Record<string, string> = {
  critical: "#dc2626", high: "#b45309", medium: "#0f5cc0", low: "#4e657a",
};
const SUITE_TYPE_COLORS: Record<string, string> = {
  smoke: "#16a34a", regression: "#0f5cc0", feature_specific: "#7c3aed",
  release_candidate: "#dc2626", agent_specific: "#0891b2",
  ui_consistency: "#d97706", safety: "#b91c1c", custom: "#4e657a",
};

interface NewRunModalProps {
  suiteId: string;
  suiteName: string;
  onClose: () => void;
  onCreated: (runId: string) => void;
}

function NewRunModal({ suiteId, suiteName, onClose, onCreated }: NewRunModalProps) {
  const [form, setForm] = useState({ title: `${suiteName} — Run`, environment: "development", triggered_by: "manual", notes: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true); setError("");
    try {
      const res = await fetch(`${BACKEND}/qa/runs`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ suite_id: suiteId, org_id: "default", run_type: "manual", ...form }),
      });
      if (!res.ok) throw new Error(`Server error (${res.status})`);
      const run = await res.json();
      onCreated(run.run_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start run.");
    } finally {
      setSaving(false);
    }
  }

  const inputStyle: React.CSSProperties = { padding: "7px 10px", borderRadius: 8, border: "1px solid var(--line)", background: "var(--surface-2)", color: "var(--text)", fontSize: "0.875rem", width: "100%", boxSizing: "border-box" };

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }}>
      <div style={{ background: "var(--surface)", borderRadius: 14, width: 460, boxShadow: "0 20px 60px rgba(0,0,0,0.2)" }}>
        <div style={{ padding: "16px 22px", borderBottom: "1px solid var(--line)", display: "flex", justifyContent: "space-between" }}>
          <h2 style={{ margin: 0, fontSize: "1rem", fontWeight: 700 }}>Start Test Run</h2>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", fontSize: "1.2rem", color: "var(--muted)" }}>×</button>
        </div>
        <form onSubmit={submit}>
          <div style={{ padding: "16px 22px", display: "flex", flexDirection: "column", gap: 12 }}>
            {[
              { key: "title", label: "Run Title" },
              { key: "environment", label: "Environment", opts: ["development", "staging", "production"] },
              { key: "triggered_by", label: "Triggered By" },
            ].map(({ key, label, opts }) => (
              <div key={key} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>{label}</span>
                {opts ? (
                  <select value={(form as Record<string, string>)[key]} onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))} style={inputStyle}>
                    {opts.map((o) => <option key={o} value={o}>{o}</option>)}
                  </select>
                ) : (
                  <input value={(form as Record<string, string>)[key]} onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))} style={inputStyle} />
                )}
              </div>
            ))}
            {error && <div style={{ color: "var(--danger)", fontSize: "0.82rem" }}>⚠ {error}</div>}
          </div>
          <div style={{ padding: "12px 22px", borderTop: "1px solid var(--line)", display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <button type="button" onClick={onClose} style={{ padding: "7px 16px", borderRadius: 8, border: "1px solid var(--line)", background: "transparent", color: "var(--text)", fontSize: "0.875rem", cursor: "pointer" }}>Cancel</button>
            <button type="submit" disabled={saving} style={{ padding: "7px 18px", borderRadius: 8, border: "none", background: "var(--success)", color: "#fff", fontSize: "0.875rem", fontWeight: 600, cursor: "pointer", opacity: saving ? 0.6 : 1 }}>
              {saving ? "Starting…" : "Start Run"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function SuiteDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [suite, setSuite] = useState<Suite | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [showRunModal, setShowRunModal] = useState(false);

  useEffect(() => {
    if (!id) return;
    Promise.all([
      fetch(`${BACKEND}/qa/suites/${id}`).then((r) => r.ok ? r.json() : null),
      fetch(`${BACKEND}/qa/runs?org_id=default&suite_id=${id}`).then((r) => r.ok ? r.json() : []),
    ]).then(([s, r]) => { setSuite(s); setRuns(r); }).finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return <PageShell title="Loading…" breadcrumbs={[{ label: "QA Registry", href: "/qa" }, { label: "Suites", href: "/qa/suites" }]}><div style={{ padding: 40, color: "var(--muted)" }}>Loading…</div></PageShell>;
  }
  if (!suite) {
    return <PageShell title="Not Found" breadcrumbs={[{ label: "QA Registry", href: "/qa" }, { label: "Suites", href: "/qa/suites" }]}><div style={{ padding: 40, color: "var(--danger)" }}>Suite not found.</div></PageShell>;
  }

  const color = SUITE_TYPE_COLORS[suite.suite_type] ?? "var(--muted)";

  return (
    <PageShell
      title={suite.name}
      subtitle={`${suite.test_case_ids.length} tests · ${suite.suite_type.replace(/_/g, " ")}`}
      breadcrumbs={[
        { label: "QA Registry", href: "/qa" },
        { label: "Suites", href: "/qa/suites" },
        { label: suite.name },
      ]}
      headerActions={
        <button onClick={() => setShowRunModal(true)} style={{ padding: "7px 16px", borderRadius: 8, border: "none", background: "var(--success)", color: "#fff", fontSize: "0.85rem", cursor: "pointer", fontWeight: 600 }}>
          ▶ Start Run
        </button>
      }
    >
      {showRunModal && suite && (
        <NewRunModal
          suiteId={suite.suite_id}
          suiteName={suite.name}
          onClose={() => setShowRunModal(false)}
          onCreated={(runId) => router.push(`/qa/runs/${runId}`)}
        />
      )}

      <div style={{ padding: "20px 28px", maxWidth: 980 }}>
        {/* Suite meta */}
        <div style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 12, padding: "16px 20px", marginBottom: 20 }}>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 10 }}>
            <span style={{ background: `${color}18`, color, border: `1px solid ${color}40`, borderRadius: 6, padding: "2px 9px", fontSize: "0.75rem", fontWeight: 700 }}>
              {suite.suite_type.replace(/_/g, " ").toUpperCase()}
            </span>
            {suite.generated_by_rule && (
              <span style={{ fontSize: "0.75rem", color: "var(--muted)", background: "var(--surface-2)", border: "1px solid var(--line)", borderRadius: 5, padding: "2px 8px" }}>
                Rule: {suite.generated_by_rule}
              </span>
            )}
          </div>
          {suite.description && <p style={{ margin: "0 0 10px", fontSize: "0.875rem", color: "var(--muted)", lineHeight: 1.5 }}>{suite.description}</p>}
          <div style={{ display: "flex", gap: 20, fontSize: "0.78rem", color: "var(--muted)" }}>
            {suite.owner && <span>Owner: <strong style={{ color: "var(--text)" }}>{suite.owner}</strong></span>}
            <span>Created: {new Date(suite.created_at).toLocaleDateString()}</span>
            {suite.feature_areas.length > 0 && (
              <span>Areas: {suite.feature_areas.join(", ")}</span>
            )}
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 20 }}>
          {/* Test cases */}
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <h3 style={{ margin: 0, fontSize: "0.9rem", fontWeight: 700 }}>
                Test Cases ({suite.test_cases?.length ?? suite.test_case_ids.length})
              </h3>
            </div>
            <div style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 12, overflow: "hidden" }}>
              {!suite.test_cases || suite.test_cases.length === 0 ? (
                <div style={{ padding: "30px", textAlign: "center", color: "var(--muted)" }}>
                  No test cases in this suite yet.
                </div>
              ) : (
                suite.test_cases.map((tc, i) => (
                  <Link key={tc.tc_id} href={`/qa/tests/${tc.tc_id}`} style={{ textDecoration: "none" }}>
                    <div
                      style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", borderBottom: i < suite.test_cases.length - 1 ? "1px solid var(--line)" : "none" }}
                      onMouseOver={(e) => { (e.currentTarget as HTMLElement).style.background = "var(--surface-2)"; }}
                      onMouseOut={(e) => { (e.currentTarget as HTMLElement).style.background = "transparent"; }}
                    >
                      <span style={{ background: `${TYPE_COLORS[tc.test_type] ?? "var(--muted)"}18`, color: TYPE_COLORS[tc.test_type] ?? "var(--muted)", border: `1px solid ${TYPE_COLORS[tc.test_type] ?? "var(--muted)"}40`, borderRadius: 5, padding: "1px 6px", fontSize: "0.7rem", fontWeight: 600, flexShrink: 0 }}>
                        {tc.test_type}
                      </span>
                      <span style={{ flex: 1, fontSize: "0.875rem", fontWeight: 500, color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{tc.title}</span>
                      {tc.release_blocker && <span style={{ fontSize: "0.72rem" }}>🔴</span>}
                      <span style={{ background: `${PRIORITY_COLORS[tc.priority] ?? "var(--muted)"}18`, color: PRIORITY_COLORS[tc.priority] ?? "var(--muted)", borderRadius: 5, padding: "1px 6px", fontSize: "0.7rem", fontWeight: 600, flexShrink: 0 }}>
                        {tc.priority}
                      </span>
                    </div>
                  </Link>
                ))
              )}
            </div>
          </div>

          {/* Runs sidebar */}
          <div>
            <h3 style={{ margin: "0 0 10px", fontSize: "0.9rem", fontWeight: 700 }}>Recent Runs</h3>
            <div style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 12, overflow: "hidden" }}>
              {runs.length === 0 ? (
                <div style={{ padding: "20px", textAlign: "center", color: "var(--muted)", fontSize: "0.85rem" }}>
                  No runs yet.<br />
                  <button onClick={() => setShowRunModal(true)} style={{ marginTop: 8, padding: "6px 14px", borderRadius: 7, border: "none", background: "var(--success)", color: "#fff", fontSize: "0.8rem", cursor: "pointer" }}>
                    Start first run
                  </button>
                </div>
              ) : (
                runs.slice(0, 10).map((run, i) => {
                  const total = run.pass_count + run.fail_count + run.blocked_count + run.not_run_count;
                  const passPct = total > 0 ? Math.round((run.pass_count / total) * 100) : 0;
                  return (
                    <Link key={run.run_id} href={`/qa/runs/${run.run_id}`} style={{ textDecoration: "none" }}>
                      <div
                        style={{ padding: "12px 14px", borderBottom: i < runs.length - 1 ? "1px solid var(--line)" : "none" }}
                        onMouseOver={(e) => { (e.currentTarget as HTMLElement).style.background = "var(--surface-2)"; }}
                        onMouseOut={(e) => { (e.currentTarget as HTMLElement).style.background = "transparent"; }}
                      >
                        <div style={{ fontSize: "0.82rem", fontWeight: 600, color: "var(--text)", marginBottom: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{run.title}</div>
                        <div style={{ display: "flex", gap: 8, fontSize: "0.72rem" }}>
                          <span style={{ color: "#16a34a" }}>✓ {run.pass_count}</span>
                          <span style={{ color: "#dc2626" }}>✗ {run.fail_count}</span>
                          <span style={{ color: "#b45309" }}>⊘ {run.blocked_count}</span>
                          <span style={{ color: "var(--muted)", marginLeft: "auto" }}>{passPct}% pass</span>
                        </div>
                        <div style={{ marginTop: 5, height: 4, background: "var(--surface-2)", borderRadius: 2, overflow: "hidden" }}>
                          <div style={{ width: `${passPct}%`, height: "100%", background: "#16a34a", borderRadius: 2 }} />
                        </div>
                      </div>
                    </Link>
                  );
                })
              )}
            </div>
          </div>
        </div>
      </div>
    </PageShell>
  );
}
