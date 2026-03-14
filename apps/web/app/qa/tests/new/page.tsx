"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { PageShell } from "../../../../components/page-shell";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const FEATURE_AREAS = [
  "chat", "agent_orchestration", "documents", "okrs", "workspaces",
  "navigation", "approvals", "ui_consistency", "provenance",
  "permissions", "memory", "analytics", "processes",
];

const TEST_TYPES = [
  "smoke", "regression", "deep", "edge", "ux",
  "safety", "data_integrity", "orchestration", "document_quality",
];

export default function NewTestCasePage() {
  const router = useRouter();
  const [form, setForm] = useState({
    title: "", feature_area: "chat", subfeature: "", test_type: "regression",
    description: "", preconditions: "", steps: "", expected_result: "",
    priority: "medium", severity_if_fails: "major", status: "draft",
    release_blocker: false, notes: "", tags: "", applies_to_agents: "", applies_to_ui_surfaces: "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.type === "checkbox" ? (e.target as HTMLInputElement).checked : e.target.value }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.title.trim()) { setError("Title is required."); return; }
    setSaving(true); setError("");
    try {
      const body = {
        ...form,
        steps: form.steps.split("\n").filter((s) => s.trim()),
        tags: form.tags.split(",").map((t) => t.trim()).filter(Boolean),
        applies_to_agents: form.applies_to_agents.split(",").map((t) => t.trim()).filter(Boolean),
        applies_to_ui_surfaces: form.applies_to_ui_surfaces.split(",").map((t) => t.trim()).filter(Boolean),
        created_by: "qa-specialist",
      };
      const res = await fetch(`${BACKEND}/qa/tests`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`Server error (${res.status})`);
      const tc = await res.json();
      router.push(`/qa/tests/${tc.tc_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create test case.");
    } finally {
      setSaving(false);
    }
  }

  const inputStyle: React.CSSProperties = {
    padding: "7px 10px", borderRadius: 8, border: "1px solid var(--line)",
    background: "var(--surface-2)", color: "var(--text)", fontSize: "0.875rem",
    fontFamily: "inherit", width: "100%", boxSizing: "border-box",
  };
  const selectStyle = { ...inputStyle };
  const labelStyle: React.CSSProperties = {
    fontSize: "0.72rem", fontWeight: 700, color: "var(--muted)",
    textTransform: "uppercase" as const, letterSpacing: "0.05em",
  };

  return (
    <PageShell
      title="New Test Case"
      subtitle="Add a structured test case to the QA registry"
      breadcrumbs={[
        { label: "QA Registry", href: "/qa" },
        { label: "Test Cases", href: "/qa/tests" },
        { label: "New" },
      ]}
    >
      <div style={{ padding: "20px 28px", maxWidth: 780 }}>
        <form onSubmit={submit}>
          <div style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 12, padding: "20px 24px", display: "flex", flexDirection: "column", gap: 16 }}>

            <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 16, alignItems: "start" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                <span style={labelStyle}>Title *</span>
                <input value={form.title} onChange={set("title")} placeholder="Clear, descriptive test case title" style={inputStyle} />
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                <span style={labelStyle}>Status</span>
                <select value={form.status} onChange={set("status")} style={{ ...selectStyle, width: 130 }}>
                  <option value="draft">Draft</option>
                  <option value="active">Active</option>
                </select>
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 12 }}>
              {[
                { key: "feature_area", label: "Feature Area", opts: FEATURE_AREAS },
                { key: "test_type", label: "Test Type", opts: TEST_TYPES },
                { key: "priority", label: "Priority", opts: ["critical", "high", "medium", "low"] },
                { key: "severity_if_fails", label: "Severity If Fails", opts: ["blocker", "critical", "major", "minor", "trivial"] },
              ].map(({ key, label, opts }) => (
                <div key={key} style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                  <span style={labelStyle}>{label}</span>
                  <select value={(form as Record<string, string>)[key]} onChange={set(key)} style={selectStyle}>
                    {opts.map((o) => <option key={o} value={o}>{o.replace(/_/g, " ")}</option>)}
                  </select>
                </div>
              ))}
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                <span style={labelStyle}>Subfeature</span>
                <input value={form.subfeature} onChange={set("subfeature")} placeholder="Optional subfeature name" style={inputStyle} />
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                <span style={labelStyle}>Tags (comma-separated)</span>
                <input value={form.tags} onChange={set("tags")} placeholder="smoke, core, auth" style={inputStyle} />
              </div>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              <span style={labelStyle}>Description</span>
              <textarea rows={3} value={form.description} onChange={set("description")} placeholder="What does this test verify and why does it matter?" style={{ ...inputStyle, resize: "vertical" }} />
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              <span style={labelStyle}>Preconditions</span>
              <textarea rows={2} value={form.preconditions} onChange={set("preconditions")} placeholder="What must be true before running this test?" style={{ ...inputStyle, resize: "vertical" }} />
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              <span style={labelStyle}>Steps (one per line)</span>
              <textarea rows={6} value={form.steps} onChange={set("steps")} placeholder={"1. Open the chat interface\n2. Type: 'What are our Q1 priorities?'\n3. Submit the message"} style={{ ...inputStyle, resize: "vertical" }} />
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              <span style={labelStyle}>Expected Result</span>
              <textarea rows={3} value={form.expected_result} onChange={set("expected_result")} placeholder="What should happen if this test passes?" style={{ ...inputStyle, resize: "vertical" }} />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                <span style={labelStyle}>Applies to Agents (comma-separated)</span>
                <input value={form.applies_to_agents} onChange={set("applies_to_agents")} placeholder="chief_of_staff, okr_coach" style={inputStyle} />
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                <span style={labelStyle}>Applies to UI Surfaces (comma-separated)</span>
                <input value={form.applies_to_ui_surfaces} onChange={set("applies_to_ui_surfaces")} placeholder="chat, okrs, workspaces" style={inputStyle} />
              </div>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              <span style={labelStyle}>Notes</span>
              <textarea rows={2} value={form.notes} onChange={set("notes")} placeholder="Any additional context, known flakiness, or caveats" style={{ ...inputStyle, resize: "vertical" }} />
            </div>

            <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
              <input type="checkbox" checked={form.release_blocker} onChange={set("release_blocker")} />
              <span style={{ fontSize: "0.875rem", fontWeight: 500 }}>This test must pass before any release (Release Blocker)</span>
            </label>

            {error && (
              <div style={{ padding: "10px 14px", borderRadius: 8, background: "#fef2f2", border: "1px solid #fca5a5", color: "var(--danger)", fontSize: "0.85rem" }}>
                ⚠ {error}
              </div>
            )}

            <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", paddingTop: 4 }}>
              <button type="button" onClick={() => router.back()} style={{ padding: "8px 18px", borderRadius: 8, border: "1px solid var(--line)", background: "transparent", color: "var(--text)", fontSize: "0.875rem", cursor: "pointer" }}>
                Cancel
              </button>
              <button type="submit" disabled={saving} style={{ padding: "8px 20px", borderRadius: 8, border: "none", background: "var(--accent)", color: "#fff", fontSize: "0.875rem", fontWeight: 600, cursor: "pointer", opacity: saving ? 0.6 : 1 }}>
                {saving ? "Creating…" : "Create Test Case"}
              </button>
            </div>
          </div>
        </form>
      </div>
    </PageShell>
  );
}
