"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { PageShell } from "../../../../components/page-shell";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface TestCase {
  tc_id: string;
  org_id: string;
  title: string;
  feature_area: string;
  subfeature: string;
  description: string;
  preconditions: string;
  steps: string[];
  expected_result: string;
  priority: string;
  severity_if_fails: string;
  test_type: string;
  applies_to_agents: string[];
  applies_to_ui_surfaces: string[];
  release_blocker: boolean;
  status: string;
  created_by: string;
  updated_by: string;
  created_at: string;
  updated_at: string;
  linked_user_story_ids: string[];
  linked_bug_ids: string[];
  linked_workspace_ids: string[];
  notes: string;
  tags: string[];
}

const TYPE_COLORS: Record<string, string> = {
  smoke: "#16a34a", regression: "#0f5cc0", deep: "#7c3aed", edge: "#b45309",
  ux: "#0891b2", safety: "#dc2626", data_integrity: "#9333ea",
  orchestration: "#059669", document_quality: "#d97706",
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
      borderRadius: 6, padding: "2px 9px", fontSize: "0.75rem", fontWeight: 600,
    }}>
      {label}
    </span>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
      <span style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
        {label}
      </span>
      <div style={{ fontSize: "0.875rem", color: "var(--text)" }}>{children}</div>
    </div>
  );
}

function EditField({
  label, value, onChange, multiline = false,
}: {
  label: string; value: string; onChange: (v: string) => void; multiline?: boolean;
}) {
  const style: React.CSSProperties = {
    width: "100%", padding: "7px 10px", borderRadius: 8, border: "1px solid var(--line)",
    background: "var(--surface-2)", color: "var(--text)", fontSize: "0.875rem",
    fontFamily: "inherit", resize: multiline ? "vertical" : undefined,
    boxSizing: "border-box",
  };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
      <span style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
        {label}
      </span>
      {multiline ? (
        <textarea rows={4} value={value} onChange={(e) => onChange(e.target.value)} style={style} />
      ) : (
        <input value={value} onChange={(e) => onChange(e.target.value)} style={style} />
      )}
    </div>
  );
}

export default function TestCaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [tc, setTc] = useState<TestCase | null>(null);
  const [loading, setLoading] = useState(true);
  const [editMode, setEditMode] = useState(false);
  const [form, setForm] = useState<Partial<TestCase>>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");

  useEffect(() => {
    if (!id) return;
    fetch(`${BACKEND}/qa/tests/${id}`)
      .then((r) => r.ok ? r.json() : null)
      .then((d) => { setTc(d); setForm(d ?? {}); })
      .catch(() => setTc(null))
      .finally(() => setLoading(false));
  }, [id]);

  async function save() {
    if (!tc) return;
    setSaving(true); setSaveError("");
    try {
      const updates: Record<string, unknown> = {};
      const editable = ["title", "feature_area", "subfeature", "description", "preconditions",
        "expected_result", "priority", "severity_if_fails", "test_type", "status", "notes",
        "release_blocker", "steps", "applies_to_agents", "applies_to_ui_surfaces", "tags"];
      for (const k of editable) {
        if (form[k as keyof TestCase] !== undefined) updates[k] = form[k as keyof TestCase];
      }
      const res = await fetch(`${BACKEND}/qa/tests/${tc.tc_id}?updated_by=qa-specialist`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates),
      });
      if (!res.ok) throw new Error(`Server error (${res.status})`);
      const updated = await res.json();
      setTc(updated); setForm(updated); setEditMode(false);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function deprecate() {
    if (!tc || !confirm("Deprecate this test case?")) return;
    await fetch(`${BACKEND}/qa/tests/${tc.tc_id}/deprecate?updated_by=qa-specialist`, { method: "POST" });
    setTc({ ...tc, status: "deprecated" });
  }

  async function clone() {
    if (!tc) return;
    const res = await fetch(`${BACKEND}/qa/tests/${tc.tc_id}/clone?created_by=qa-specialist`, { method: "POST" });
    if (res.ok) {
      const cloned = await res.json();
      router.push(`/qa/tests/${cloned.tc_id}`);
    }
  }

  const set = (k: keyof TestCase) => (v: unknown) => setForm((f) => ({ ...f, [k]: v }));

  if (loading) {
    return (
      <PageShell title="Test Case" breadcrumbs={[{ label: "QA Registry", href: "/qa" }, { label: "Test Cases", href: "/qa/tests" }, { label: "Loading…" }]}>
        <div style={{ padding: 40, color: "var(--muted)" }}>Loading…</div>
      </PageShell>
    );
  }

  if (!tc) {
    return (
      <PageShell title="Not Found" breadcrumbs={[{ label: "QA Registry", href: "/qa" }, { label: "Test Cases", href: "/qa/tests" }]}>
        <div style={{ padding: 40 }}>
          <div style={{ color: "var(--danger)", marginBottom: 12 }}>Test case not found.</div>
          <Link href="/qa/tests" style={{ color: "var(--accent)" }}>← Back to test cases</Link>
        </div>
      </PageShell>
    );
  }

  const headerActions = (
    <div style={{ display: "flex", gap: 8 }}>
      {!editMode ? (
        <>
          <button onClick={clone} style={{ padding: "6px 14px", borderRadius: 8, border: "1px solid var(--line)", background: "transparent", color: "var(--text)", fontSize: "0.82rem", cursor: "pointer" }}>
            Clone
          </button>
          {tc.status !== "deprecated" && (
            <button onClick={deprecate} style={{ padding: "6px 14px", borderRadius: 8, border: "1px solid var(--line)", background: "transparent", color: "var(--warning)", fontSize: "0.82rem", cursor: "pointer" }}>
              Deprecate
            </button>
          )}
          <button onClick={() => setEditMode(true)} style={{ padding: "6px 14px", borderRadius: 8, border: "none", background: "var(--accent)", color: "#fff", fontSize: "0.82rem", cursor: "pointer" }}>
            Edit
          </button>
        </>
      ) : (
        <>
          <button onClick={() => { setEditMode(false); setForm(tc); setSaveError(""); }} style={{ padding: "6px 14px", borderRadius: 8, border: "1px solid var(--line)", background: "transparent", color: "var(--text)", fontSize: "0.82rem", cursor: "pointer" }}>
            Cancel
          </button>
          <button onClick={save} disabled={saving} style={{ padding: "6px 14px", borderRadius: 8, border: "none", background: "var(--success)", color: "#fff", fontSize: "0.82rem", cursor: "pointer", opacity: saving ? 0.6 : 1 }}>
            {saving ? "Saving…" : "Save Changes"}
          </button>
        </>
      )}
    </div>
  );

  return (
    <PageShell
      title={editMode ? "Editing Test Case" : tc.title}
      subtitle={`${tc.tc_id} · ${tc.feature_area.replace(/_/g, " ")}`}
      breadcrumbs={[
        { label: "QA Registry", href: "/qa" },
        { label: "Test Cases", href: "/qa/tests" },
        { label: tc.title },
      ]}
      headerActions={headerActions}
    >
      <div style={{ padding: "20px 28px", maxWidth: 900 }}>
        {saveError && (
          <div style={{ padding: "10px 14px", borderRadius: 8, background: "#fef2f2", border: "1px solid #fca5a5", color: "var(--danger)", fontSize: "0.85rem", marginBottom: 16 }}>
            ⚠ {saveError}
          </div>
        )}

        {/* Status/meta row */}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 20, alignItems: "center" }}>
          <Pill label={tc.status} color={STATUS_COLORS[tc.status] ?? "var(--muted)"} />
          <Pill label={tc.test_type.replace(/_/g, " ")} color={TYPE_COLORS[tc.test_type] ?? "var(--muted)"} />
          <Pill label={tc.priority} color={PRIORITY_COLORS[tc.priority] ?? "var(--muted)"} />
          {tc.release_blocker && <Pill label="🔴 Release Blocker" color="#dc2626" />}
          <span style={{ marginLeft: "auto", fontSize: "0.75rem", color: "var(--muted)" }}>
            Updated {new Date(tc.updated_at).toLocaleDateString()} by {tc.updated_by}
          </span>
        </div>

        {editMode ? (
          /* ── Edit Mode ─────────────────────────────────────────── */
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <EditField label="Title" value={form.title ?? ""} onChange={set("title")} />
              <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                <span style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Status</span>
                <select value={form.status ?? ""} onChange={(e) => set("status")(e.target.value)}
                  style={{ padding: "7px 10px", borderRadius: 8, border: "1px solid var(--line)", background: "var(--surface-2)", color: "var(--text)", fontSize: "0.875rem" }}>
                  <option value="draft">Draft</option>
                  <option value="active">Active</option>
                  <option value="deprecated">Deprecated</option>
                </select>
              </div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 12 }}>
              {["feature_area", "test_type", "priority", "severity_if_fails"].map((k) => (
                <EditField key={k} label={k.replace(/_/g, " ")} value={(form as Record<string, string>)[k] ?? ""} onChange={set(k as keyof TestCase)} />
              ))}
            </div>
            <EditField label="Subfeature" value={form.subfeature ?? ""} onChange={set("subfeature")} />
            <EditField label="Description" value={form.description ?? ""} onChange={set("description")} multiline />
            <EditField label="Preconditions" value={form.preconditions ?? ""} onChange={set("preconditions")} multiline />
            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              <span style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Steps (one per line)</span>
              <textarea
                rows={6}
                value={(form.steps ?? []).join("\n")}
                onChange={(e) => set("steps")(e.target.value.split("\n").filter((s) => s.trim()))}
                style={{ width: "100%", padding: "7px 10px", borderRadius: 8, border: "1px solid var(--line)", background: "var(--surface-2)", color: "var(--text)", fontSize: "0.875rem", fontFamily: "inherit", resize: "vertical", boxSizing: "border-box" }}
              />
            </div>
            <EditField label="Expected Result" value={form.expected_result ?? ""} onChange={set("expected_result")} multiline />
            <EditField label="Notes" value={form.notes ?? ""} onChange={set("notes")} multiline />
            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              <span style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Release Blocker</span>
              <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
                <input type="checkbox" checked={form.release_blocker ?? false} onChange={(e) => set("release_blocker")(e.target.checked)} />
                <span style={{ fontSize: "0.875rem" }}>This test must pass before any release</span>
              </label>
            </div>
          </div>
        ) : (
          /* ── View Mode ─────────────────────────────────────────── */
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            {/* Details card */}
            <div style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 12, padding: "18px 20px" }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 16, marginBottom: 16 }}>
                <Field label="Feature Area">{tc.feature_area.replace(/_/g, " ")}</Field>
                <Field label="Subfeature">{tc.subfeature || <span style={{ color: "var(--muted)" }}>—</span>}</Field>
                <Field label="Test Type">{tc.test_type.replace(/_/g, " ")}</Field>
                <Field label="Priority">{tc.priority}</Field>
                <Field label="Severity if Fails">{tc.severity_if_fails}</Field>
                <Field label="Created By">{tc.created_by}</Field>
                <Field label="Created">{new Date(tc.created_at).toLocaleDateString()}</Field>
                <Field label="Tags">
                  {tc.tags.length > 0
                    ? <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                        {tc.tags.map((t) => (
                          <span key={t} style={{ background: "var(--surface-2)", border: "1px solid var(--line)", borderRadius: 5, padding: "1px 6px", fontSize: "0.72rem", color: "var(--muted)" }}>{t}</span>
                        ))}
                      </div>
                    : <span style={{ color: "var(--muted)" }}>—</span>
                  }
                </Field>
              </div>

              {tc.description && <Field label="Description"><span style={{ lineHeight: 1.6 }}>{tc.description}</span></Field>}
            </div>

            {/* Steps & expected */}
            <div style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 12, padding: "18px 20px" }}>
              <h3 style={{ margin: "0 0 12px", fontSize: "0.9rem", fontWeight: 700 }}>Test Procedure</h3>
              {tc.preconditions && (
                <div style={{ marginBottom: 14, padding: "10px 14px", background: "#fffbeb", border: "1px solid #fcd34d", borderRadius: 8 }}>
                  <div style={{ fontSize: "0.72rem", fontWeight: 700, color: "#b45309", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>Preconditions</div>
                  <div style={{ fontSize: "0.85rem" }}>{tc.preconditions}</div>
                </div>
              )}
              {tc.steps.length > 0 ? (
                <ol style={{ paddingLeft: 20, margin: "0 0 14px", display: "flex", flexDirection: "column", gap: 6 }}>
                  {tc.steps.map((step, i) => (
                    <li key={i} style={{ fontSize: "0.875rem", lineHeight: 1.5 }}>{step}</li>
                  ))}
                </ol>
              ) : (
                <div style={{ color: "var(--muted)", fontSize: "0.85rem", marginBottom: 14 }}>No steps defined.</div>
              )}
              {tc.expected_result && (
                <div style={{ padding: "10px 14px", background: "#f0fdf4", border: "1px solid #86efac", borderRadius: 8 }}>
                  <div style={{ fontSize: "0.72rem", fontWeight: 700, color: "#16a34a", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>Expected Result</div>
                  <div style={{ fontSize: "0.85rem" }}>{tc.expected_result}</div>
                </div>
              )}
            </div>

            {/* Agents & Surfaces */}
            {(tc.applies_to_agents.length > 0 || tc.applies_to_ui_surfaces.length > 0) && (
              <div style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 12, padding: "16px 20px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                <Field label="Applies to Agents">
                  {tc.applies_to_agents.length > 0
                    ? <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                        {tc.applies_to_agents.map((a) => <span key={a} style={{ background: "#ede9fe", color: "#7c3aed", border: "1px solid #c4b5fd", borderRadius: 5, padding: "1px 6px", fontSize: "0.75rem" }}>{a}</span>)}
                      </div>
                    : <span style={{ color: "var(--muted)" }}>All agents</span>
                  }
                </Field>
                <Field label="Applies to UI Surfaces">
                  {tc.applies_to_ui_surfaces.length > 0
                    ? <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                        {tc.applies_to_ui_surfaces.map((s) => <span key={s} style={{ background: "#e0f2fe", color: "#0891b2", border: "1px solid #7dd3fc", borderRadius: 5, padding: "1px 6px", fontSize: "0.75rem" }}>{s}</span>)}
                      </div>
                    : <span style={{ color: "var(--muted)" }}>All surfaces</span>
                  }
                </Field>
              </div>
            )}

            {/* Linked items */}
            {(tc.linked_bug_ids.length > 0 || tc.linked_user_story_ids.length > 0) && (
              <div style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 12, padding: "16px 20px" }}>
                <h3 style={{ margin: "0 0 12px", fontSize: "0.9rem", fontWeight: 700 }}>Linked Items</h3>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                  <Field label="Linked Bugs">
                    {tc.linked_bug_ids.length > 0
                      ? tc.linked_bug_ids.map((id) => <div key={id} style={{ fontSize: "0.82rem", color: "var(--danger)" }}>{id}</div>)
                      : <span style={{ color: "var(--muted)" }}>None</span>
                    }
                  </Field>
                  <Field label="Linked User Stories">
                    {tc.linked_user_story_ids.length > 0
                      ? tc.linked_user_story_ids.map((id) => <div key={id} style={{ fontSize: "0.82rem", color: "var(--accent)" }}>{id}</div>)
                      : <span style={{ color: "var(--muted)" }}>None</span>
                    }
                  </Field>
                </div>
              </div>
            )}

            {/* Notes */}
            {tc.notes && (
              <div style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 12, padding: "16px 20px" }}>
                <Field label="Notes"><span style={{ lineHeight: 1.6 }}>{tc.notes}</span></Field>
              </div>
            )}
          </div>
        )}
      </div>
    </PageShell>
  );
}
