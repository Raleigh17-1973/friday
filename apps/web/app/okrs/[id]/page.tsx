"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { PageShell } from "@/components/page-shell";

const API = "http://localhost:8000";

interface KeyResult {
  kr_id: string;
  title: string;
  metric_type: string;
  baseline: number;
  current_value: number;
  target_value: number;
  unit: string;
  owner: string;
  data_source: string;
  update_cadence: string;
  status: string;
  confidence: number;
  due_date: string;
  notes: string;
  risk_flags: string[];
  kpi_id?: string | null;
}

interface KPIOption {
  kpi_id: string;
  name: string;
  unit: string;
}

interface Initiative {
  initiative_id: string;
  title: string;
  owner: string;
  kr_id: string | null;
  status: string;
  due_date: string;
  description: string;
}

interface CheckIn {
  checkin_id: string;
  author: string;
  status: string;
  confidence: number;
  highlights: string;
  blockers: string;
  next_steps: string;
  created_at: string;
}

interface ObjectiveDetail {
  obj_id: string;
  title: string;
  description: string;
  owner: string;
  level: string;
  parent_id: string | null;
  period: string;
  status: string;
  confidence: number;
  progress: number;
  rationale: string;
  collaborators: string[];
  workspace_id: string | null;
  key_results: KeyResult[];
  initiatives: Initiative[];
  checkins: CheckIn[];
  created_at: string;
}

const STATUS_BADGE: Record<string, string> = {
  on_track: "badge badge-success",
  at_risk: "badge badge-warning",
  behind: "badge badge-danger",
  completed: "badge badge-neutral",
  active: "badge badge-info",
  cancelled: "badge badge-neutral",
  not_started: "badge badge-neutral",
  in_progress: "badge badge-info",
  done: "badge badge-success",
  blocked: "badge badge-danger",
};

const METRIC_ICON: Record<string, string> = {
  percentage: "%",
  number: "#",
  currency: "$",
  boolean: "✓",
};

const LEVEL_COLOR: Record<string, string> = {
  company: "#6366f1",
  team: "#8b5cf6",
  individual: "#22c55e",
};

function statusLabel(s: string | undefined | null) {
  if (!s) return "—";
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function ProgressBar({ value, status }: { value: number; status: string }) {
  const fillClass =
    status === "on_track" ? "on-track" : status === "at_risk" ? "at-risk" : status === "behind" ? "behind" : "";
  return (
    <div className="progress-bar-wrap">
      <div
        className={`progress-bar-fill ${fillClass}`}
        style={{ width: `${Math.min(100, Math.round(Math.max(0, value) * 100))}%` }}
      />
    </div>
  );
}

// ── Edit Objective Form ────────────────────────────────────────────────────
function EditObjectiveForm({ obj, onDone }: { obj: ObjectiveDetail; onDone: () => void }) {
  const [form, setForm] = useState({
    title: obj.title,
    description: obj.description || "",
    owner: obj.owner || "",
    status: obj.status,
    confidence: Math.round(obj.confidence * 100),
    period: obj.period || "",
    level: obj.level,
    rationale: obj.rationale || "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const res = await fetch(`${API}/okrs/${obj.obj_id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...form,
          confidence: form.confidence / 100,
        }),
      });
      if (!res.ok) throw new Error("Failed to save");
      onDone();
    } catch {
      setError("Failed to save. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  const inp = (field: keyof typeof form) => ({
    className: "form-input",
    value: form[field],
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
      setForm({ ...form, [field]: e.target.value }),
  });

  return (
    <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
        <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.82rem", fontWeight: 600 }}>
          Title
          <input {...inp("title")} required />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.82rem", fontWeight: 600 }}>
          Owner
          <input {...inp("owner")} placeholder="e.g. Jane Smith" />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.82rem", fontWeight: 600 }}>
          Status
          <select {...inp("status")} className="form-select">
            <option value="active">Active</option>
            <option value="on_track">On Track</option>
            <option value="at_risk">At Risk</option>
            <option value="behind">Behind</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.82rem", fontWeight: 600 }}>
          Level
          <select {...inp("level")} className="form-select">
            <option value="company">Company</option>
            <option value="team">Team</option>
            <option value="individual">Individual</option>
          </select>
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.82rem", fontWeight: 600 }}>
          Period
          <input {...inp("period")} placeholder="e.g. 2025-Q1" />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.82rem", fontWeight: 600 }}>
          Confidence (%)
          <input type="number" min={0} max={100} {...inp("confidence")} className="form-input" />
        </label>
      </div>
      <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.82rem", fontWeight: 600 }}>
        Description
        <textarea {...inp("description")} className="form-input" rows={2} style={{ resize: "vertical" }} />
      </label>
      <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.82rem", fontWeight: 600 }}>
        Why It Matters (Rationale)
        <textarea {...inp("rationale")} className="form-input" rows={2} style={{ resize: "vertical" }} />
      </label>
      {error && <p style={{ color: "#dc2626", fontSize: "0.82rem", margin: 0 }}>{error}</p>}
      <div style={{ display: "flex", gap: "0.5rem" }}>
        <button type="submit" className="btn btn-primary btn-sm" disabled={saving}>{saving ? "Saving…" : "Save Changes"}</button>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onDone}>Cancel</button>
      </div>
    </form>
  );
}

// ── Add KR Form ────────────────────────────────────────────────────────────
function AddKRForm({ objId, onDone }: { objId: string; onDone: () => void }) {
  const [form, setForm] = useState({
    title: "",
    metric_type: "number",
    baseline: 0,
    target_value: 100,
    unit: "",
    owner: "",
    due_date: "",
  });
  const [saving, setSaving] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await fetch(`${API}/okrs/${objId}/key-results`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      onDone();
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} style={{ background: "var(--bg)", border: "1px solid var(--border)", borderRadius: "0.5rem", padding: "1rem", marginTop: "0.75rem" }}>
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr", gap: "0.5rem", marginBottom: "0.5rem" }}>
        <input className="form-input" placeholder="Key result title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required />
        <select className="form-select" value={form.metric_type} onChange={(e) => setForm({ ...form, metric_type: e.target.value })}>
          <option value="number">Number</option>
          <option value="percentage">Percentage</option>
          <option value="currency">Currency</option>
          <option value="boolean">Boolean</option>
        </select>
        <input className="form-input" placeholder="Unit (e.g. %, USD)" value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })} />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: "0.5rem", marginBottom: "0.5rem" }}>
        <input className="form-input" type="number" placeholder="Baseline" value={form.baseline} onChange={(e) => setForm({ ...form, baseline: +e.target.value })} />
        <input className="form-input" type="number" placeholder="Target" value={form.target_value} onChange={(e) => setForm({ ...form, target_value: +e.target.value })} />
        <input className="form-input" placeholder="Owner" value={form.owner} onChange={(e) => setForm({ ...form, owner: e.target.value })} />
        <input className="form-input" type="date" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} />
      </div>
      <div style={{ display: "flex", gap: "0.5rem" }}>
        <button type="submit" className="btn btn-primary btn-sm" disabled={saving}>{saving ? "Saving…" : "Add Key Result"}</button>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onDone}>Cancel</button>
      </div>
    </form>
  );
}

// ── Update KR Form ─────────────────────────────────────────────────────────
function UpdateKRForm({ kr, kpis, onDone }: { kr: KeyResult; kpis: KPIOption[]; onDone: () => void }) {
  const [form, setForm] = useState({
    current_value: kr.current_value,
    status: kr.status,
    notes: kr.notes || "",
    kpi_id: kr.kpi_id ?? "",
  });
  const [saving, setSaving] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await fetch(`${API}/okrs/key-results/${kr.kr_id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_value: form.current_value,
          status: form.status,
          notes: form.notes,
          kpi_id: form.kpi_id || null,
        }),
      });
      onDone();
    } finally {
      setSaving(false);
    }
  }

  const range = kr.target_value - kr.baseline;
  const pct = range !== 0 ? Math.round(((form.current_value - kr.baseline) / range) * 100) : 0;

  return (
    <form onSubmit={submit} style={{ background: "var(--bg)", border: "1px solid var(--border)", borderRadius: "0.5rem", padding: "0.875rem", marginTop: "0.5rem" }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.5rem", marginBottom: "0.5rem" }}>
        <label style={{ display: "flex", flexDirection: "column", gap: "3px", fontSize: "0.78rem", fontWeight: 600 }}>
          Current Value
          <input
            className="form-input"
            type="number"
            value={form.current_value}
            onChange={(e) => setForm({ ...form, current_value: +e.target.value })}
          />
          <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
            {kr.baseline} → {form.current_value} / {kr.target_value} {kr.unit} ({pct}%)
          </span>
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: "3px", fontSize: "0.78rem", fontWeight: 600 }}>
          Status
          <select className="form-select" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
            <option value="active">Active</option>
            <option value="on_track">On Track</option>
            <option value="at_risk">At Risk</option>
            <option value="behind">Behind</option>
            <option value="completed">Completed</option>
          </select>
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: "3px", fontSize: "0.78rem", fontWeight: 600 }}>
          Notes
          <input
            className="form-input"
            placeholder="Update notes…"
            value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
          />
        </label>
      </div>
      {kpis.length > 0 && (
        <label style={{ display: "flex", flexDirection: "column", gap: "3px", fontSize: "0.78rem", fontWeight: 600, marginBottom: "0.5rem" }}>
          Link to KPI (auto-sync)
          <select
            className="form-select"
            value={form.kpi_id}
            onChange={(e) => setForm({ ...form, kpi_id: e.target.value })}
            style={{ maxWidth: 320 }}
          >
            <option value="">— No KPI link —</option>
            {kpis.map((k) => (
              <option key={k.kpi_id} value={k.kpi_id}>
                {k.name} ({k.unit})
              </option>
            ))}
          </select>
          <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
            When a new KPI data point is recorded, this KR's value updates automatically.
          </span>
        </label>
      )}
      <div style={{ display: "flex", gap: "0.5rem" }}>
        <button type="submit" className="btn btn-primary btn-sm" disabled={saving}>{saving ? "Saving…" : "Update Progress"}</button>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onDone}>Cancel</button>
      </div>
    </form>
  );
}

// ── Add Initiative Form ────────────────────────────────────────────────────
function AddInitiativeForm({ objId, onDone }: { objId: string; onDone: () => void }) {
  const [form, setForm] = useState({ title: "", owner: "", status: "not_started", due_date: "", description: "" });
  const [saving, setSaving] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await fetch(`${API}/okrs/${objId}/initiatives`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, org_id: "default" }),
      });
      onDone();
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} style={{ background: "var(--bg)", border: "1px solid var(--border)", borderRadius: "0.5rem", padding: "1rem", marginTop: "0.75rem" }}>
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr", gap: "0.5rem", marginBottom: "0.5rem" }}>
        <input className="form-input" placeholder="Initiative title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required />
        <input className="form-input" placeholder="Owner" value={form.owner} onChange={(e) => setForm({ ...form, owner: e.target.value })} />
        <select className="form-select" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
          <option value="not_started">Not Started</option>
          <option value="in_progress">In Progress</option>
          <option value="done">Done</option>
          <option value="blocked">Blocked</option>
        </select>
        <input className="form-input" type="date" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} />
      </div>
      <div style={{ display: "flex", gap: "0.5rem" }}>
        <button type="submit" className="btn btn-primary btn-sm" disabled={saving}>{saving ? "Saving…" : "Add Initiative"}</button>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onDone}>Cancel</button>
      </div>
    </form>
  );
}

// ── Update Initiative inline ───────────────────────────────────────────────
function UpdateInitiativeRow({ init, onDone }: { init: Initiative; onDone: () => void }) {
  const [status, setStatus] = useState(init.status);
  const [owner, setOwner] = useState(init.owner || "");
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      await fetch(`${API}/okrs/initiatives/${init.initiative_id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status, owner }),
      });
      onDone();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.5rem", background: "var(--bg)", borderRadius: "0.375rem", marginTop: "0.25rem" }}>
      <select className="form-select" value={status} onChange={(e) => setStatus(e.target.value)} style={{ width: 140 }}>
        <option value="not_started">Not Started</option>
        <option value="in_progress">In Progress</option>
        <option value="done">Done</option>
        <option value="blocked">Blocked</option>
      </select>
      <input className="form-input" placeholder="Owner" value={owner} onChange={(e) => setOwner(e.target.value)} style={{ width: 140 }} />
      <button className="btn btn-primary btn-sm" onClick={save} disabled={saving}>{saving ? "…" : "Save"}</button>
      <button className="btn btn-ghost btn-sm" onClick={onDone}>Cancel</button>
    </div>
  );
}

// ── Add Check-in Form ──────────────────────────────────────────────────────
function AddCheckInForm({ objId, onDone }: { objId: string; onDone: () => void }) {
  const [form, setForm] = useState({
    author: "",
    status: "on_track",
    confidence: 70,
    highlights: "",
    blockers: "",
    next_steps: "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.author.trim() || !form.highlights.trim()) {
      setError("Author and highlights are required.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const res = await fetch(`${API}/okrs/${objId}/check-in`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, confidence: form.confidence / 100 }),
      });
      if (!res.ok) throw new Error("Failed to submit");
      onDone();
    } catch {
      setError("Failed to submit check-in. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} style={{ background: "var(--bg)", border: "1px solid var(--border)", borderRadius: "0.5rem", padding: "1rem" }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.5rem", marginBottom: "0.75rem" }}>
        <label style={{ display: "flex", flexDirection: "column", gap: "3px", fontSize: "0.82rem", fontWeight: 600 }}>
          Author <input className="form-input" placeholder="Your name" value={form.author} onChange={(e) => setForm({ ...form, author: e.target.value })} required />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: "3px", fontSize: "0.82rem", fontWeight: 600 }}>
          Status
          <select className="form-select" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
            <option value="on_track">On Track</option>
            <option value="at_risk">At Risk</option>
            <option value="behind">Behind</option>
            <option value="completed">Completed</option>
          </select>
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: "3px", fontSize: "0.82rem", fontWeight: 600 }}>
          Confidence ({form.confidence}%)
          <input type="range" min={0} max={100} step={5} value={form.confidence} onChange={(e) => setForm({ ...form, confidence: +e.target.value })} style={{ marginTop: "4px" }} />
        </label>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", marginBottom: "0.75rem" }}>
        <label style={{ display: "flex", flexDirection: "column", gap: "3px", fontSize: "0.82rem", fontWeight: 600 }}>
          ✅ Highlights — what progress was made?
          <textarea className="form-input" rows={2} value={form.highlights} onChange={(e) => setForm({ ...form, highlights: e.target.value })} placeholder="Key accomplishments this period…" style={{ resize: "vertical" }} required />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: "3px", fontSize: "0.82rem", fontWeight: 600 }}>
          🚧 Blockers (optional)
          <textarea className="form-input" rows={2} value={form.blockers} onChange={(e) => setForm({ ...form, blockers: e.target.value })} placeholder="Any blockers or risks…" style={{ resize: "vertical" }} />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: "3px", fontSize: "0.82rem", fontWeight: 600 }}>
          → Next Steps (optional)
          <textarea className="form-input" rows={2} value={form.next_steps} onChange={(e) => setForm({ ...form, next_steps: e.target.value })} placeholder="Planned actions for next period…" style={{ resize: "vertical" }} />
        </label>
      </div>
      {error && <p style={{ color: "#dc2626", fontSize: "0.82rem", margin: "0 0 0.5rem" }}>{error}</p>}
      <div style={{ display: "flex", gap: "0.5rem" }}>
        <button type="submit" className="btn btn-primary btn-sm" disabled={saving}>{saving ? "Submitting…" : "Submit Check-in"}</button>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onDone}>Cancel</button>
      </div>
    </form>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────
export default function OKRDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [obj, setObj] = useState<ObjectiveDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [kpis, setKpis] = useState<KPIOption[]>([]);
  const [editingObj, setEditingObj] = useState(false);
  const [showAddKR, setShowAddKR] = useState(false);
  const [editingKR, setEditingKR] = useState<string | null>(null);
  const [showAddInit, setShowAddInit] = useState(false);
  const [editingInit, setEditingInit] = useState<string | null>(null);
  const [showAddCheckIn, setShowAddCheckIn] = useState(false);
  const [showAllCheckIns, setShowAllCheckIns] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [showGradeForm, setShowGradeForm] = useState(false);
  const [gradeValue, setGradeValue] = useState(0.7);
  const [gradeRetro, setGradeRetro] = useState("");
  const [gradeCarryForward, setGradeCarryForward] = useState(false);
  const [grading, setGrading] = useState(false);
  const [gradeResult, setGradeResult] = useState<{ grade_label?: string; carry_forward_obj_id?: string } | null>(null);

  // Fetch available KPIs for the link-to-KPI select
  useEffect(() => {
    fetch(`${API}/kpis?org_id=org-1`)
      .then((r) => r.json())
      .then((data: KPIOption[]) => { if (Array.isArray(data)) setKpis(data); })
      .catch(() => undefined);
  }, []);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/okrs/${id}`);
      if (res.status === 404) { setError("Objective not found"); return; }
      if (!res.ok) throw new Error("Failed to load");
      const data = await res.json() as {
        objective?: ObjectiveDetail;
        key_results?: KeyResult[];
        initiatives?: Initiative[];
        checkins?: CheckIn[];
      } & ObjectiveDetail;
      if (data.objective) {
        setObj({
          ...data.objective,
          key_results: data.key_results ?? [],
          initiatives: data.initiatives ?? [],
          checkins: data.checkins ?? [],
        });
      } else {
        setObj(data as ObjectiveDetail);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error loading");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [id]);

  async function handleGrade(e: React.FormEvent) {
    e.preventDefault();
    if (!obj || grading) return;
    setGrading(true);
    try {
      const res = await fetch(`${API}/okrs/${obj.obj_id}/grade`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          grade: gradeValue,
          retrospective: gradeRetro,
          carry_forward: gradeCarryForward,
        }),
      });
      if (!res.ok) throw new Error("Grade failed");
      const data = await res.json() as { grade_label?: string; carry_forward_obj_id?: string };
      setGradeResult(data);
      setShowGradeForm(false);
      load();
    } catch {
      // swallow
    } finally {
      setGrading(false);
    }
  }

  async function handleExport(format: "docx" | "pptx" = "docx") {
    if (!obj || exporting) return;
    setExporting(true);
    try {
      const res = await fetch(`${API}/okrs/${obj.obj_id}/export?format=${format}&org_id=org-1`);
      if (!res.ok) throw new Error("Export failed");
      const data = await res.json() as { download_url: string; filename: string };
      window.open(`${API}${data.download_url}`, "_blank", "noopener,noreferrer");
    } catch {
      // swallow — user sees nothing happen, which is acceptable for an export action
    } finally {
      setExporting(false);
    }
  }

  if (loading) {
    return (
      <PageShell title="Loading…" breadcrumbs={[{ label: "OKRs", href: "/okrs" }, { label: "…" }]}>
        <div className="loading-skeleton">
          {[...Array(6)].map((_, i) => <div key={i} className="loading-skeleton-row" />)}
        </div>
      </PageShell>
    );
  }

  if (error || !obj) {
    return (
      <PageShell title="Not Found" breadcrumbs={[{ label: "OKRs", href: "/okrs" }]}>
        <div className="error-state">
          <div style={{ fontSize: "2rem" }}>🎯</div>
          <div>{error || "Objective not found"}</div>
          <Link href="/okrs" className="btn btn-secondary btn-sm">← Back to OKRs</Link>
        </div>
      </PageShell>
    );
  }

  const krProgress =
    obj.key_results.length > 0
      ? obj.key_results.reduce((sum, kr) => {
          const range = kr.target_value - kr.baseline;
          return sum + (range !== 0 ? (kr.current_value - kr.baseline) / range : 0);
        }, 0) / obj.key_results.length
      : obj.progress;

  const visibleCheckIns = showAllCheckIns ? obj.checkins : obj.checkins.slice(0, 5);

  return (
    <PageShell
      title={obj.title}
      breadcrumbs={[{ label: "OKRs", href: "/okrs" }, { label: obj.title }]}
      subtitle={`${obj.period} · ${obj.level} objective`}
      headerActions={
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => handleExport("docx")}
            disabled={exporting}
            title="Export as Word document"
          >
            {exporting ? "Exporting…" : "↓ Export"}
          </button>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => { setEditingObj(true); }}
          >
            ✏️ Edit Objective
          </button>
        </div>
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>

        {/* Overview card */}
        <div className="card">
          <div className="card-header">
            Overview
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <span className={STATUS_BADGE[obj.status] || "badge badge-neutral"}>{statusLabel(obj.status)}</span>
              <span className="badge" style={{ background: LEVEL_COLOR[obj.level] + "22", color: LEVEL_COLOR[obj.level] }}>{obj.level}</span>
            </div>
          </div>
          <div className="card-body">
            {editingObj ? (
              <EditObjectiveForm
                obj={obj}
                onDone={() => { setEditingObj(false); load(); }}
              />
            ) : (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem" }}>
                <div>
                  {obj.description && <p style={{ color: "var(--text)", marginBottom: "1rem", lineHeight: 1.6 }}>{obj.description}</p>}
                  {obj.rationale && (
                    <div style={{ background: "var(--bg)", border: "1px solid var(--border)", borderRadius: "0.5rem", padding: "0.75rem", marginBottom: "1rem" }}>
                      <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-muted)", marginBottom: "0.25rem", textTransform: "uppercase" }}>Why it matters</div>
                      <div style={{ fontSize: "0.875rem", color: "var(--text)", lineHeight: 1.5 }}>{obj.rationale}</div>
                    </div>
                  )}
                  {obj.parent_id && (
                    <div style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>
                      Parent: <Link href={`/okrs/${obj.parent_id}`} style={{ color: "var(--accent)" }}>View parent objective →</Link>
                    </div>
                  )}
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  <div>
                    <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-muted)", marginBottom: "0.375rem" }}>OWNER</div>
                    <div style={{ fontSize: "0.9375rem", fontWeight: 500 }}>{obj.owner || "—"}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-muted)", marginBottom: "0.375rem" }}>PROGRESS</div>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                      <ProgressBar value={krProgress} status={obj.status} />
                      <span style={{ fontSize: "0.9375rem", fontWeight: 600 }}>{Math.round(krProgress * 100)}%</span>
                    </div>
                    {obj.key_results.length > 0 && (
                      <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>
                        Auto-computed from {obj.key_results.length} key result{obj.key_results.length !== 1 ? "s" : ""}
                      </div>
                    )}
                  </div>
                  <div>
                    <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-muted)", marginBottom: "0.375rem" }}>CONFIDENCE</div>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                      <div className="progress-bar-wrap">
                        <div
                          className="progress-bar-fill"
                          style={{
                            width: `${Math.round(obj.confidence * 100)}%`,
                            background: obj.confidence >= 0.7 ? "#16a34a" : obj.confidence >= 0.4 ? "#d97706" : "#dc2626",
                          }}
                        />
                      </div>
                      <span style={{ fontSize: "0.9375rem", fontWeight: 600 }}>{Math.round(obj.confidence * 100)}%</span>
                    </div>
                  </div>
                  {obj.collaborators.length > 0 && (
                    <div>
                      <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-muted)", marginBottom: "0.375rem" }}>COLLABORATORS</div>
                      <div style={{ display: "flex", gap: "0.375rem", flexWrap: "wrap" }}>
                        {obj.collaborators.map((c) => (
                          <span key={c} className="badge badge-neutral">{c}</span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Key Results */}
        <div className="card">
          <div className="card-header">
            Key Results
            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
              <span className="badge badge-neutral">{obj.key_results.length}</span>
              <button className="btn btn-secondary btn-sm" onClick={() => setShowAddKR((v) => !v)}>
                {showAddKR ? "Cancel" : "+ Add KR"}
              </button>
            </div>
          </div>
          <div className="card-body">
            {obj.key_results.length === 0 && !showAddKR ? (
              <div className="empty-state" style={{ padding: "2rem" }}>
                <div className="empty-state-icon">📊</div>
                <p className="empty-state-title">No key results yet</p>
                <p className="empty-state-body">Add measurable outcomes to track progress toward this objective.</p>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                {obj.key_results.map((kr) => {
                  const range = kr.target_value - kr.baseline;
                  const progress = range !== 0 ? (kr.current_value - kr.baseline) / range : 0;
                  const isEditing = editingKR === kr.kr_id;
                  const linkedKpi = kr.kpi_id ? kpis.find((k) => k.kpi_id === kr.kpi_id) : null;
                  return (
                    <div key={kr.kr_id} style={{ border: "1px solid var(--border)", borderRadius: "0.5rem", padding: "1rem" }}>
                      <div style={{ display: "flex", alignItems: "flex-start", gap: "0.75rem", marginBottom: "0.625rem" }}>
                        <span style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "0.25rem", padding: "0.125rem 0.4rem", fontFamily: "monospace", fontSize: "0.75rem", color: "var(--accent)", flexShrink: 0 }}>
                          {METRIC_ICON[kr.metric_type] || "#"}
                        </span>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontWeight: 500, color: "var(--text)", marginBottom: "0.375rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                            {kr.title}
                            {linkedKpi && (
                              <span style={{ fontSize: "0.7rem", background: "#ecfdf5", color: "#16a34a", border: "1px solid #bbf7d0", borderRadius: "9999px", padding: "1px 8px", fontWeight: 600 }}>
                                ⚡ Auto-synced from {linkedKpi.name}
                              </span>
                            )}
                          </div>
                          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                            <ProgressBar value={progress} status={kr.status} />
                            <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", whiteSpace: "nowrap" }}>
                              {kr.baseline} → <strong>{kr.current_value}</strong> / {kr.target_value} {kr.unit}
                            </span>
                          </div>
                        </div>
                        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "0.25rem", flexShrink: 0 }}>
                          <span className={STATUS_BADGE[kr.status] || "badge badge-neutral"}>{statusLabel(kr.status)}</span>
                          {kr.due_date && <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Due {kr.due_date.slice(0, 10)}</span>}
                          <button
                            className="btn btn-ghost btn-sm"
                            style={{ fontSize: "0.72rem", padding: "2px 8px" }}
                            onClick={() => setEditingKR(isEditing ? null : kr.kr_id)}
                          >
                            {isEditing ? "Cancel" : "Update Progress"}
                          </button>
                        </div>
                      </div>
                      <div style={{ display: "flex", gap: "1rem", fontSize: "0.8125rem", color: "var(--text-muted)" }}>
                        {kr.owner && <span>Owner: {kr.owner}</span>}
                        {kr.update_cadence && <span>Updates: {kr.update_cadence}</span>}
                        {kr.data_source && <span>Source: {kr.data_source}</span>}
                      </div>
                      {kr.notes && <div style={{ fontSize: "0.8125rem", color: "var(--text-muted)", marginTop: "0.5rem", fontStyle: "italic" }}>{kr.notes}</div>}
                      {kr.risk_flags && kr.risk_flags.length > 0 && (
                        <div style={{ marginTop: "0.5rem", display: "flex", gap: "0.375rem" }}>
                          {kr.risk_flags.map((f) => <span key={f} className="badge badge-warning">⚠ {f}</span>)}
                        </div>
                      )}
                      {isEditing && (
                        <UpdateKRForm
                          kr={kr}
                          kpis={kpis}
                          onDone={() => { setEditingKR(null); load(); }}
                        />
                      )}
                    </div>
                  );
                })}
              </div>
            )}
            {showAddKR && <AddKRForm objId={obj.obj_id} onDone={() => { setShowAddKR(false); load(); }} />}
          </div>
        </div>

        {/* Initiatives */}
        <div className="card">
          <div className="card-header">
            Initiatives
            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
              <span className="badge badge-neutral">{obj.initiatives.length}</span>
              <button className="btn btn-secondary btn-sm" onClick={() => setShowAddInit((v) => !v)}>
                {showAddInit ? "Cancel" : "+ Add Initiative"}
              </button>
            </div>
          </div>
          <div className="card-body">
            {obj.initiatives.length === 0 && !showAddInit ? (
              <div className="empty-state" style={{ padding: "2rem" }}>
                <div className="empty-state-icon">🚀</div>
                <p className="empty-state-title">No initiatives yet</p>
                <p className="empty-state-body">Initiatives are the activities that drive your key results.</p>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
                {obj.initiatives.map((init) => {
                  const isEditing = editingInit === init.initiative_id;
                  return (
                    <div key={init.initiative_id}>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", padding: "0.625rem 0", borderBottom: "1px solid var(--border)" }}>
                        <span className={STATUS_BADGE[init.status] || "badge badge-neutral"}>{statusLabel(init.status)}</span>
                        <span style={{ flex: 1, fontSize: "0.875rem", color: "var(--text)", fontWeight: 500 }}>{init.title}</span>
                        {init.owner && <span style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>{init.owner}</span>}
                        {init.due_date && <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", whiteSpace: "nowrap" }}>Due {init.due_date.slice(0, 10)}</span>}
                        <button
                          className="btn btn-ghost btn-sm"
                          style={{ fontSize: "0.72rem", padding: "2px 8px" }}
                          onClick={() => setEditingInit(isEditing ? null : init.initiative_id)}
                        >
                          {isEditing ? "Cancel" : "Edit"}
                        </button>
                      </div>
                      {isEditing && (
                        <UpdateInitiativeRow
                          init={init}
                          onDone={() => { setEditingInit(null); load(); }}
                        />
                      )}
                    </div>
                  );
                })}
              </div>
            )}
            {showAddInit && <AddInitiativeForm objId={obj.obj_id} onDone={() => { setShowAddInit(false); load(); }} />}
          </div>
        </div>

        {/* Check-in Log */}
        <div className="card">
          <div className="card-header">
            Weekly Check-ins
            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
              {obj.checkins.length > 0 && <span className="badge badge-neutral">{obj.checkins.length}</span>}
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setShowAddCheckIn((v) => !v)}
              >
                {showAddCheckIn ? "Cancel" : "+ Log Update"}
              </button>
            </div>
          </div>
          <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {showAddCheckIn && (
              <AddCheckInForm
                objId={obj.obj_id}
                onDone={() => { setShowAddCheckIn(false); load(); }}
              />
            )}
            {obj.checkins.length === 0 && !showAddCheckIn ? (
              <div className="empty-state" style={{ padding: "1.5rem" }}>
                <div className="empty-state-icon">📝</div>
                <p className="empty-state-title">No check-ins yet</p>
                <p className="empty-state-body">Log regular updates to track momentum and surface blockers early.</p>
              </div>
            ) : (
              <>
                {visibleCheckIns.map((ci) => (
                  <div key={ci.checkin_id} style={{ borderLeft: "3px solid var(--accent)", paddingLeft: "1rem" }}>
                    <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", marginBottom: "0.375rem", flexWrap: "wrap" }}>
                      <span className={STATUS_BADGE[ci.status] || "badge badge-neutral"}>{statusLabel(ci.status)}</span>
                      <span style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>{ci.author}</span>
                      <span style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>·</span>
                      <span style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>{new Date(ci.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}</span>
                      <span style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>·</span>
                      <span style={{ fontSize: "0.8125rem", color: ci.confidence >= 0.7 ? "#16a34a" : ci.confidence >= 0.4 ? "#d97706" : "#dc2626" }}>
                        {Math.round(ci.confidence * 100)}% confidence
                      </span>
                    </div>
                    {ci.highlights && <div style={{ fontSize: "0.875rem", marginBottom: "0.25rem" }}><strong>✅</strong> {ci.highlights}</div>}
                    {ci.blockers && <div style={{ fontSize: "0.875rem", color: "#dc2626", marginBottom: "0.25rem" }}><strong>🚧</strong> {ci.blockers}</div>}
                    {ci.next_steps && <div style={{ fontSize: "0.875rem", color: "var(--text-muted)" }}><strong>→</strong> {ci.next_steps}</div>}
                  </div>
                ))}
                {obj.checkins.length > 5 && (
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() => setShowAllCheckIns((v) => !v)}
                    style={{ alignSelf: "flex-start" }}
                  >
                    {showAllCheckIns ? "Show fewer" : `Show all ${obj.checkins.length} check-ins`}
                  </button>
                )}
              </>
            )}
          </div>
        </div>
        {/* Grade This Objective */}
        {(obj.status === "completed" || obj.status === "graded" || obj.progress >= 1) && (
          <div className="card">
            <div className="card-header">
              Grade This Objective
              {obj.status !== "graded" && (
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => setShowGradeForm((v) => !v)}
                >
                  {showGradeForm ? "Cancel" : "Grade"}
                </button>
              )}
            </div>
            <div className="card-body">
              {gradeResult && (
                <div style={{ padding: "0.75rem", background: "var(--surface-2)", borderRadius: "var(--radius-s)", marginBottom: "1rem" }}>
                  ✅ Graded: <strong>{gradeResult.grade_label}</strong>
                  {gradeResult.carry_forward_obj_id && (
                    <span> · <a href={`/okrs/${gradeResult.carry_forward_obj_id}`} style={{ color: "var(--accent)" }}>View carried-forward objective →</a></span>
                  )}
                </div>
              )}
              {showGradeForm && (
                <form onSubmit={handleGrade} style={{ display: "flex", flexDirection: "column", gap: "0.75rem", maxWidth: 520 }}>
                  <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.82rem", fontWeight: 600 }}>
                    Grade (0.0 – 1.0)
                    <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
                      <input
                        type="range" min={0} max={1} step={0.05}
                        value={gradeValue}
                        onChange={(e) => setGradeValue(Number(e.target.value))}
                        style={{ flex: 1 }}
                      />
                      <span style={{ fontWeight: 700, minWidth: 40 }}>{Math.round(gradeValue * 100)}%</span>
                    </div>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 400 }}>
                      {gradeValue < 0.1 ? "Did Not Start" : gradeValue < 0.45 ? "Partial" : gradeValue < 0.75 ? "Good Progress" : "Fully Achieved"}
                    </span>
                  </label>
                  <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.82rem", fontWeight: 600 }}>
                    Retrospective
                    <textarea
                      className="form-input"
                      rows={3}
                      placeholder="What went well? What would you do differently?"
                      value={gradeRetro}
                      onChange={(e) => setGradeRetro(e.target.value)}
                    />
                  </label>
                  <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.82rem", fontWeight: 600, cursor: "pointer" }}>
                    <input
                      type="checkbox"
                      checked={gradeCarryForward}
                      onChange={(e) => setGradeCarryForward(e.target.checked)}
                    />
                    Carry forward into next period
                  </label>
                  <button className="btn btn-primary" type="submit" disabled={grading} style={{ alignSelf: "flex-start" }}>
                    {grading ? "Saving…" : "Submit Grade"}
                  </button>
                </form>
              )}
              {obj.status === "graded" && !showGradeForm && !gradeResult && (
                <p style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>This objective has been graded.</p>
              )}
            </div>
          </div>
        )}
      </div>
    </PageShell>
  );
}
