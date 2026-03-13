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

function statusLabel(s: string) {
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

export default function OKRDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [obj, setObj] = useState<ObjectiveDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showAddKR, setShowAddKR] = useState(false);
  const [showAddInit, setShowAddInit] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/okrs/${id}`);
      if (res.status === 404) { setError("Objective not found"); return; }
      if (!res.ok) throw new Error("Failed to load");
      const data = await res.json();
      setObj(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error loading");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [id]);

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

  return (
    <PageShell
      title={obj.title}
      breadcrumbs={[{ label: "OKRs", href: "/okrs" }, { label: obj.title }]}
      subtitle={`${obj.period} · ${obj.level} objective`}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>

        {/* Summary card */}
        <div className="card">
          <div className="card-header">
            Overview
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <span className={STATUS_BADGE[obj.status] || "badge badge-neutral"}>{statusLabel(obj.status)}</span>
              <span className="badge" style={{ background: LEVEL_COLOR[obj.level] + "22", color: LEVEL_COLOR[obj.level] }}>{obj.level}</span>
            </div>
          </div>
          <div className="card-body">
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
                  return (
                    <div key={kr.kr_id} style={{ border: "1px solid var(--border)", borderRadius: "0.5rem", padding: "1rem" }}>
                      <div style={{ display: "flex", alignItems: "flex-start", gap: "0.75rem", marginBottom: "0.625rem" }}>
                        <span style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "0.25rem", padding: "0.125rem 0.4rem", fontFamily: "monospace", fontSize: "0.75rem", color: "var(--accent)", flexShrink: 0 }}>
                          {METRIC_ICON[kr.metric_type] || "#"}
                        </span>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontWeight: 500, color: "var(--text)", marginBottom: "0.375rem" }}>{kr.title}</div>
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
              <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                {obj.initiatives.map((init) => (
                  <div key={init.initiative_id} style={{ display: "flex", alignItems: "center", gap: "0.75rem", padding: "0.625rem 0", borderBottom: "1px solid var(--border)" }}>
                    <span className={STATUS_BADGE[init.status] || "badge badge-neutral"}>{statusLabel(init.status)}</span>
                    <span style={{ flex: 1, fontSize: "0.875rem", color: "var(--text)", fontWeight: 500 }}>{init.title}</span>
                    {init.owner && <span style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>{init.owner}</span>}
                    {init.due_date && <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", whiteSpace: "nowrap" }}>Due {init.due_date.slice(0, 10)}</span>}
                  </div>
                ))}
              </div>
            )}
            {showAddInit && <AddInitiativeForm objId={obj.obj_id} onDone={() => { setShowAddInit(false); load(); }} />}
          </div>
        </div>

        {/* Check-in log */}
        {obj.checkins && obj.checkins.length > 0 && (
          <div className="card">
            <div className="card-header">Check-in Log</div>
            <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              {obj.checkins.slice(0, 5).map((ci) => (
                <div key={ci.checkin_id} style={{ borderLeft: "3px solid var(--accent)", paddingLeft: "1rem" }}>
                  <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", marginBottom: "0.375rem" }}>
                    <span className={STATUS_BADGE[ci.status] || "badge badge-neutral"}>{statusLabel(ci.status)}</span>
                    <span style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>{ci.author} · {ci.created_at.slice(0, 10)}</span>
                    <span style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>Confidence: {Math.round(ci.confidence * 100)}%</span>
                  </div>
                  {ci.highlights && <div style={{ fontSize: "0.875rem", marginBottom: "0.25rem" }}><strong>✅</strong> {ci.highlights}</div>}
                  {ci.blockers && <div style={{ fontSize: "0.875rem", color: "#dc2626", marginBottom: "0.25rem" }}><strong>🚧</strong> {ci.blockers}</div>}
                  {ci.next_steps && <div style={{ fontSize: "0.875rem", color: "var(--text-muted)" }}><strong>→</strong> {ci.next_steps}</div>}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </PageShell>
  );
}
