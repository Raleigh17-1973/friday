"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { PageShell } from "../../../components/page-shell";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
}

const SUITE_TYPE_COLORS: Record<string, string> = {
  smoke: "#16a34a", regression: "#0f5cc0", feature_specific: "#7c3aed",
  release_candidate: "#dc2626", agent_specific: "#0891b2",
  ui_consistency: "#d97706", safety: "#b91c1c", custom: "#4e657a",
};

const SUITE_TYPES = [
  "smoke", "regression", "feature_specific", "release_candidate",
  "agent_specific", "ui_consistency", "safety", "custom",
];

const FEATURE_AREAS = [
  "chat", "agent_orchestration", "documents", "okrs", "workspaces",
  "navigation", "approvals", "ui_consistency", "provenance",
  "permissions", "memory", "analytics", "processes",
];

interface NewSuiteModalProps {
  onClose: () => void;
  onCreated: () => void;
}

function NewSuiteModal({ onClose, onCreated }: NewSuiteModalProps) {
  const [mode, setMode] = useState<"manual" | "generate">("manual");
  const [form, setForm] = useState({
    name: "", suite_type: "custom", description: "",
    feature_areas: [] as string[], owner: "",
  });
  const [rule, setRule] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const set = (k: string) => (v: string) => setForm((f) => ({ ...f, [k]: v }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) { setError("Name is required."); return; }
    setSaving(true); setError("");
    try {
      const url = mode === "generate" ? `${BACKEND}/qa/suites/generate` : `${BACKEND}/qa/suites`;
      const body = mode === "generate"
        ? { name: form.name, rule, org_id: "default", owner: form.owner }
        : { ...form, org_id: "default" };
      const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      if (!res.ok) throw new Error(`Server error (${res.status})`);
      onCreated(); onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create suite.");
    } finally {
      setSaving(false);
    }
  }

  const inputStyle: React.CSSProperties = { padding: "7px 10px", borderRadius: 8, border: "1px solid var(--line)", background: "var(--surface-2)", color: "var(--text)", fontSize: "0.875rem", fontFamily: "inherit", width: "100%", boxSizing: "border-box" };

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }}>
      <div style={{ background: "var(--surface)", borderRadius: 14, width: 520, boxShadow: "0 20px 60px rgba(0,0,0,0.2)", overflow: "hidden" }}>
        <div style={{ padding: "18px 22px", borderBottom: "1px solid var(--line)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ margin: 0, fontSize: "1rem", fontWeight: 700 }}>New Test Suite</h2>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", fontSize: "1.2rem", color: "var(--muted)" }}>×</button>
        </div>
        <form onSubmit={submit}>
          <div style={{ padding: "18px 22px", display: "flex", flexDirection: "column", gap: 14 }}>
            {/* Mode toggle */}
            <div style={{ display: "flex", gap: 8 }}>
              {(["manual", "generate"] as const).map((m) => (
                <button key={m} type="button" onClick={() => setMode(m)}
                  style={{ flex: 1, padding: "7px", borderRadius: 8, border: `1px solid ${mode === m ? "var(--accent)" : "var(--line)"}`, background: mode === m ? `rgba(15,92,192,0.08)` : "transparent", color: mode === m ? "var(--accent)" : "var(--text)", fontSize: "0.82rem", fontWeight: mode === m ? 600 : 400, cursor: "pointer" }}>
                  {m === "manual" ? "Manual Assembly" : "Generate from Rules"}
                </button>
              ))}
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              <span style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Suite Name *</span>
              <input value={form.name} onChange={(e) => set("name")(e.target.value)} placeholder="e.g. Release Candidate — Sprint 12" style={inputStyle} />
            </div>

            {mode === "generate" ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                <span style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Rule</span>
                <input value={rule} onChange={(e) => setRule(e.target.value)}
                  placeholder="feature_area=workspaces,test_type=smoke" style={inputStyle} />
                <span style={{ fontSize: "0.72rem", color: "var(--muted)" }}>
                  Combine: feature_area=X, test_type=Y, release_blocker=true, status=active
                </span>
              </div>
            ) : (
              <>
                <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                  <span style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Suite Type</span>
                  <select value={form.suite_type} onChange={(e) => set("suite_type")(e.target.value)} style={inputStyle}>
                    {SUITE_TYPES.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}</option>)}
                  </select>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                  <span style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Description</span>
                  <textarea rows={2} value={form.description} onChange={(e) => set("description")(e.target.value)} placeholder="What is this suite for?" style={{ ...inputStyle, resize: "vertical" } as React.CSSProperties} />
                </div>
              </>
            )}

            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              <span style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Owner</span>
              <input value={form.owner} onChange={(e) => set("owner")(e.target.value)} placeholder="e.g. qa-specialist" style={inputStyle} />
            </div>

            {error && <div style={{ padding: "8px 12px", borderRadius: 8, background: "#fef2f2", border: "1px solid #fca5a5", color: "var(--danger)", fontSize: "0.82rem" }}>⚠ {error}</div>}
          </div>
          <div style={{ padding: "14px 22px", borderTop: "1px solid var(--line)", display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <button type="button" onClick={onClose} style={{ padding: "7px 16px", borderRadius: 8, border: "1px solid var(--line)", background: "transparent", color: "var(--text)", fontSize: "0.875rem", cursor: "pointer" }}>Cancel</button>
            <button type="submit" disabled={saving} style={{ padding: "7px 18px", borderRadius: 8, border: "none", background: "var(--accent)", color: "#fff", fontSize: "0.875rem", fontWeight: 600, cursor: "pointer", opacity: saving ? 0.6 : 1 }}>
              {saving ? "Creating…" : mode === "generate" ? "Generate Suite" : "Create Suite"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function SuitesPage() {
  const [suites, setSuites] = useState<Suite[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);

  function load() {
    setLoading(true);
    fetch(`${BACKEND}/qa/suites?org_id=default`)
      .then((r) => r.ok ? r.json() : [])
      .then(setSuites)
      .catch(() => setSuites([]))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  const headerActions = (
    <button onClick={() => setShowModal(true)} style={{ padding: "7px 16px", borderRadius: 8, border: "none", background: "var(--accent)", color: "#fff", fontSize: "0.85rem", cursor: "pointer", fontWeight: 600 }}>
      + New Suite
    </button>
  );

  return (
    <PageShell
      title="Test Suites"
      subtitle="Organized collections of test cases for structured execution"
      breadcrumbs={[{ label: "QA Registry", href: "/qa" }, { label: "Suites" }]}
      headerActions={headerActions}
    >
      {showModal && <NewSuiteModal onClose={() => setShowModal(false)} onCreated={load} />}
      <div style={{ padding: "20px 28px" }}>
        {loading ? (
          <div style={{ color: "var(--muted)", padding: "40px 0", textAlign: "center" }}>Loading…</div>
        ) : suites.length === 0 ? (
          <div style={{ textAlign: "center", padding: "60px 0" }}>
            <div style={{ fontSize: "2.5rem", marginBottom: 12 }}>📋</div>
            <div style={{ fontWeight: 600, fontSize: "1.1rem", marginBottom: 6 }}>No test suites yet</div>
            <div style={{ color: "var(--muted)", marginBottom: 20, fontSize: "0.9rem" }}>
              Create a suite to group related test cases and run them together.
            </div>
            <button onClick={() => setShowModal(true)} style={{ padding: "9px 20px", borderRadius: 8, border: "none", background: "var(--accent)", color: "#fff", fontSize: "0.875rem", fontWeight: 600, cursor: "pointer" }}>
              + New Suite
            </button>
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 14 }}>
            {suites.map((suite) => {
              const color = SUITE_TYPE_COLORS[suite.suite_type] ?? "var(--muted)";
              return (
                <Link key={suite.suite_id} href={`/qa/suites/${suite.suite_id}`} style={{ textDecoration: "none" }}>
                  <div
                    style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 12, padding: "16px 18px", cursor: "pointer", transition: "box-shadow 0.15s" }}
                    onMouseOver={(e) => { (e.currentTarget as HTMLElement).style.boxShadow = "0 2px 8px rgba(0,0,0,0.08)"; }}
                    onMouseOut={(e) => { (e.currentTarget as HTMLElement).style.boxShadow = "none"; }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                      <span style={{ background: `${color}18`, color, border: `1px solid ${color}40`, borderRadius: 6, padding: "2px 9px", fontSize: "0.7rem", fontWeight: 700 }}>
                        {suite.suite_type.replace(/_/g, " ").toUpperCase()}
                      </span>
                      {suite.generated_by_rule && (
                        <span style={{ fontSize: "0.7rem", color: "var(--muted)", background: "var(--surface-2)", border: "1px solid var(--line)", borderRadius: 5, padding: "1px 6px" }}>
                          Auto-generated
                        </span>
                      )}
                    </div>
                    <div style={{ fontWeight: 700, fontSize: "0.95rem", color: "var(--text)", marginBottom: 4 }}>{suite.name}</div>
                    {suite.description && (
                      <div style={{ fontSize: "0.82rem", color: "var(--muted)", marginBottom: 10, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {suite.description}
                      </div>
                    )}
                    <div style={{ display: "flex", gap: 16, fontSize: "0.78rem", color: "var(--muted)" }}>
                      <span><strong style={{ color: "var(--text)" }}>{suite.test_case_ids.length}</strong> tests</span>
                      {suite.owner && <span>Owner: {suite.owner}</span>}
                      <span style={{ marginLeft: "auto" }}>{new Date(suite.created_at).toLocaleDateString()}</span>
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
