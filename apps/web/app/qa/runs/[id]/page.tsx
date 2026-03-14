"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { PageShell } from "../../../../components/page-shell";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface TestResult {
  result_id: string;
  test_case_id: string;
  result: string;
  severity: string | null;
  findings: string;
  reproduction_notes: string;
  linked_bug_id: string | null;
  should_become_regression: boolean;
  tester: string;
  timestamp: string;
}

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
  summary: string;
  notes: string;
  pass_count: number;
  fail_count: number;
  blocked_count: number;
  not_run_count: number;
  results: TestResult[];
}

interface RecordResultModalProps {
  runId: string;
  testCaseIds: string[];
  onClose: () => void;
  onSaved: () => void;
}

function RecordResultModal({ runId, testCaseIds, onClose, onSaved }: RecordResultModalProps) {
  const [form, setForm] = useState({
    test_case_id: testCaseIds[0] ?? "",
    result: "pass",
    findings: "",
    reproduction_notes: "",
    severity: "",
    tester: "",
    should_become_regression: false,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true); setError("");
    try {
      const res = await fetch(`${BACKEND}/qa/runs/${runId}/results`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, severity: form.severity || null }),
      });
      if (!res.ok) throw new Error(`Error ${res.status}`);
      onSaved(); onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setSaving(false);
    }
  }

  const inputStyle: React.CSSProperties = { padding: "7px 10px", borderRadius: 8, border: "1px solid var(--line)", background: "var(--surface-2)", color: "var(--text)", fontSize: "0.875rem", width: "100%", boxSizing: "border-box" };

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }}>
      <div style={{ background: "var(--surface)", borderRadius: 14, width: 500, boxShadow: "0 20px 60px rgba(0,0,0,0.2)" }}>
        <div style={{ padding: "16px 22px", borderBottom: "1px solid var(--line)", display: "flex", justifyContent: "space-between" }}>
          <h2 style={{ margin: 0, fontSize: "1rem", fontWeight: 700 }}>Record Test Result</h2>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", fontSize: "1.2rem", color: "var(--muted)" }}>×</button>
        </div>
        <form onSubmit={submit}>
          <div style={{ padding: "16px 22px", display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Test Case ID</span>
              <input value={form.test_case_id} onChange={(e) => setForm((f) => ({ ...f, test_case_id: e.target.value }))} style={inputStyle} placeholder="tc-..." />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Result</span>
                <select value={form.result} onChange={(e) => setForm((f) => ({ ...f, result: e.target.value }))} style={inputStyle}>
                  {["pass", "fail", "blocked", "not_run"].map((r) => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Severity (if fail)</span>
                <select value={form.severity} onChange={(e) => setForm((f) => ({ ...f, severity: e.target.value }))} style={inputStyle}>
                  <option value="">—</option>
                  {["blocker", "critical", "major", "minor", "trivial"].map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Findings</span>
              <textarea rows={3} value={form.findings} onChange={(e) => setForm((f) => ({ ...f, findings: e.target.value }))} style={{ ...inputStyle, resize: "vertical" } as React.CSSProperties} placeholder="What was observed?" />
            </div>
            {form.result === "fail" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Reproduction Notes</span>
                <textarea rows={2} value={form.reproduction_notes} onChange={(e) => setForm((f) => ({ ...f, reproduction_notes: e.target.value }))} style={{ ...inputStyle, resize: "vertical" } as React.CSSProperties} placeholder="Steps to reproduce" />
              </div>
            )}
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Tester</span>
              <input value={form.tester} onChange={(e) => setForm((f) => ({ ...f, tester: e.target.value }))} style={inputStyle} placeholder="qa-specialist" />
            </div>
            <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
              <input type="checkbox" checked={form.should_become_regression} onChange={(e) => setForm((f) => ({ ...f, should_become_regression: e.target.checked }))} />
              <span style={{ fontSize: "0.85rem" }}>Flag as regression candidate</span>
            </label>
            {error && <div style={{ color: "var(--danger)", fontSize: "0.82rem" }}>⚠ {error}</div>}
          </div>
          <div style={{ padding: "12px 22px", borderTop: "1px solid var(--line)", display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <button type="button" onClick={onClose} style={{ padding: "7px 16px", borderRadius: 8, border: "1px solid var(--line)", background: "transparent", color: "var(--text)", fontSize: "0.875rem", cursor: "pointer" }}>Cancel</button>
            <button type="submit" disabled={saving} style={{ padding: "7px 18px", borderRadius: 8, border: "none", background: "var(--accent)", color: "#fff", fontSize: "0.875rem", fontWeight: 600, cursor: "pointer", opacity: saving ? 0.6 : 1 }}>
              {saving ? "Saving…" : "Record Result"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

const RESULT_COLORS: Record<string, string> = {
  pass: "#16a34a", fail: "#dc2626", blocked: "#b45309", not_run: "#9ca3af",
};
const RESULT_ICONS: Record<string, string> = {
  pass: "✓", fail: "✗", blocked: "⊘", not_run: "—",
};

export default function RunDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [run, setRun] = useState<Run | null>(null);
  const [loading, setLoading] = useState(true);
  const [showResultModal, setShowResultModal] = useState(false);
  const [completing, setCompleting] = useState(false);

  function load() {
    if (!id) return;
    setLoading(true);
    fetch(`${BACKEND}/qa/runs/${id}`)
      .then((r) => r.ok ? r.json() : null)
      .then(setRun)
      .catch(() => setRun(null))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, [id]);

  async function completeRun() {
    if (!run) return;
    setCompleting(true);
    const res = await fetch(`${BACKEND}/qa/runs/${run.run_id}/complete?summary=Completed`, { method: "POST" });
    if (res.ok) { const updated = await res.json(); setRun({ ...updated, results: run.results }); }
    setCompleting(false);
  }

  if (loading) return <PageShell title="Loading…" breadcrumbs={[{ label: "QA Registry", href: "/qa" }, { label: "Runs", href: "/qa/runs" }]}><div style={{ padding: 40, color: "var(--muted)" }}>Loading…</div></PageShell>;
  if (!run) return <PageShell title="Not Found" breadcrumbs={[{ label: "QA Registry", href: "/qa" }, { label: "Runs", href: "/qa/runs" }]}><div style={{ padding: 40, color: "var(--danger)" }}>Run not found.</div></PageShell>;

  const total = run.pass_count + run.fail_count + run.blocked_count + run.not_run_count;
  const passPct = total > 0 ? Math.round((run.pass_count / total) * 100) : 0;
  const regressionCandidates = run.results.filter((r) => r.should_become_regression);

  return (
    <PageShell
      title={run.title}
      subtitle={`Suite: ${run.suite_id} · ${run.environment}`}
      breadcrumbs={[
        { label: "QA Registry", href: "/qa" },
        { label: "Runs", href: "/qa/runs" },
        { label: run.title },
      ]}
      headerActions={
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => setShowResultModal(true)} style={{ padding: "7px 14px", borderRadius: 8, border: "1px solid var(--line)", background: "var(--surface)", color: "var(--text)", fontSize: "0.82rem", cursor: "pointer" }}>
            + Record Result
          </button>
          {run.status === "in_progress" && (
            <button onClick={completeRun} disabled={completing} style={{ padding: "7px 14px", borderRadius: 8, border: "none", background: "var(--success)", color: "#fff", fontSize: "0.82rem", cursor: "pointer", opacity: completing ? 0.6 : 1 }}>
              {completing ? "Completing…" : "Complete Run"}
            </button>
          )}
        </div>
      }
    >
      {showResultModal && <RecordResultModal runId={run.run_id} testCaseIds={[]} onClose={() => setShowResultModal(false)} onSaved={load} />}

      <div style={{ padding: "20px 28px", maxWidth: 940 }}>
        {/* Summary bar */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12, marginBottom: 20 }}>
          {[
            { label: "Pass", count: run.pass_count, color: "#16a34a" },
            { label: "Fail", count: run.fail_count, color: "#dc2626" },
            { label: "Blocked", count: run.blocked_count, color: "#b45309" },
            { label: "Not Run", count: run.not_run_count, color: "#9ca3af" },
            { label: "Pass Rate", count: `${passPct}%`, color: passPct >= 90 ? "#16a34a" : passPct >= 70 ? "#b45309" : "#dc2626" },
          ].map(({ label, count, color }) => (
            <div key={label} style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 10, padding: "14px 16px", textAlign: "center" }}>
              <div style={{ fontSize: "1.5rem", fontWeight: 700, color, lineHeight: 1 }}>{count}</div>
              <div style={{ fontSize: "0.72rem", color: "var(--muted)", marginTop: 4, textTransform: "uppercase", letterSpacing: "0.04em" }}>{label}</div>
            </div>
          ))}
        </div>

        {/* Progress bar */}
        {total > 0 && (
          <div style={{ display: "flex", height: 8, borderRadius: 4, overflow: "hidden", background: "var(--surface-2)", marginBottom: 20 }}>
            <div style={{ width: `${(run.pass_count / total) * 100}%`, background: "#16a34a" }} />
            <div style={{ width: `${(run.fail_count / total) * 100}%`, background: "#dc2626" }} />
            <div style={{ width: `${(run.blocked_count / total) * 100}%`, background: "#b45309" }} />
          </div>
        )}

        {/* Run info */}
        <div style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 12, padding: "14px 18px", marginBottom: 20, display: "flex", gap: 24, flexWrap: "wrap", fontSize: "0.82rem", color: "var(--muted)" }}>
          <span>Status: <strong style={{ color: "var(--text)" }}>{run.status}</strong></span>
          <span>Environment: <strong style={{ color: "var(--text)" }}>{run.environment}</strong></span>
          <span>Triggered by: <strong style={{ color: "var(--text)" }}>{run.triggered_by}</strong></span>
          <span>Started: <strong style={{ color: "var(--text)" }}>{new Date(run.started_at).toLocaleString()}</strong></span>
          {run.completed_at && <span>Completed: <strong style={{ color: "var(--text)" }}>{new Date(run.completed_at).toLocaleString()}</strong></span>}
        </div>

        {/* Regression candidates */}
        {regressionCandidates.length > 0 && (
          <div style={{ background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: 12, padding: "14px 18px", marginBottom: 20 }}>
            <div style={{ fontWeight: 700, color: "#b45309", marginBottom: 8 }}>
              ⚠ {regressionCandidates.length} Regression Candidate{regressionCandidates.length > 1 ? "s" : ""} Flagged
            </div>
            {regressionCandidates.map((r) => (
              <div key={r.result_id} style={{ fontSize: "0.82rem", color: "#7c3a00", marginBottom: 4 }}>
                • {r.test_case_id}: {r.findings.substring(0, 80)}{r.findings.length > 80 ? "…" : ""}
              </div>
            ))}
          </div>
        )}

        {/* Results table */}
        <div style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 12, overflow: "hidden" }}>
          <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--line)", fontWeight: 700, fontSize: "0.875rem" }}>
            Results ({run.results.length})
          </div>
          {run.results.length === 0 ? (
            <div style={{ padding: "30px", textAlign: "center", color: "var(--muted)" }}>
              No results recorded yet.{" "}
              <button onClick={() => setShowResultModal(true)} style={{ color: "var(--accent)", background: "none", border: "none", cursor: "pointer", textDecoration: "underline" }}>
                Record the first result
              </button>
            </div>
          ) : (
            run.results.map((res, i) => {
              const color = RESULT_COLORS[res.result] ?? "var(--muted)";
              return (
                <div key={res.result_id} style={{
                  display: "grid", gridTemplateColumns: "40px 180px 1fr 80px 80px",
                  padding: "10px 16px", borderBottom: i < run.results.length - 1 ? "1px solid var(--line)" : "none",
                  alignItems: "center",
                }}>
                  <div style={{ fontWeight: 700, fontSize: "1rem", color }}>{RESULT_ICONS[res.result]}</div>
                  <div style={{ fontSize: "0.78rem", color: "var(--muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    <Link href={`/qa/tests/${res.test_case_id}`} style={{ color: "var(--accent)" }}>{res.test_case_id}</Link>
                  </div>
                  <div style={{ fontSize: "0.82rem", color: "var(--text)" }}>
                    {res.findings || <span style={{ color: "var(--muted)" }}>—</span>}
                    {res.reproduction_notes && <div style={{ fontSize: "0.72rem", color: "var(--muted)", marginTop: 2 }}>Repro: {res.reproduction_notes}</div>}
                  </div>
                  <div style={{ fontSize: "0.72rem", color: "var(--muted)" }}>{res.tester}</div>
                  <div style={{ fontSize: "0.72rem", color: "var(--muted)" }}>
                    {res.should_become_regression && <span style={{ color: "#b45309" }}>⚑ Regression</span>}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </PageShell>
  );
}
