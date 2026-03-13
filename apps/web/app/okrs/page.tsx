"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const BACKEND = process.env.NEXT_PUBLIC_FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000";

type KeyResult = {
  kr_id: string;
  title: string;
  target_value: number;
  current_value: number;
  unit: string;
  progress: number;
};

type Objective = {
  objective_id: string;
  title: string;
  description: string;
  owner: string;
  due_date: string;
  progress: number;
  status: string;
  key_results: KeyResult[];
};

type NewObjectiveForm = {
  title: string;
  description: string;
  owner: string;
  due_date: string;
};

const EMPTY_FORM: NewObjectiveForm = {
  title: "",
  description: "",
  owner: "",
  due_date: "",
};

function ProgressBar({ value, className }: { value: number; className?: string }) {
  const pct = Math.min(100, Math.max(0, Math.round(value * 100)));
  const color =
    pct >= 70 ? "var(--success)" : pct >= 40 ? "#c47d00" : "var(--danger)";
  return (
    <div className={`okr-progress-track ${className ?? ""}`} aria-label={`${pct}%`}>
      <div
        className="okr-progress-fill"
        style={{ width: `${pct}%`, backgroundColor: color }}
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
      />
      <span className="okr-progress-label">{pct}%</span>
    </div>
  );
}

function StatusChip({ status }: { status: string }) {
  return (
    <span className={`okr-status-chip okr-status-${status.toLowerCase().replace(/\s+/g, "-")}`}>
      {status}
    </span>
  );
}

function ObjectiveRow({ objective }: { objective: Objective }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <li className="okr-objective-item">
      <button
        className="okr-objective-header"
        onClick={() => setExpanded((prev) => !prev)}
        aria-expanded={expanded}
      >
        <div className="okr-objective-title-row">
          <span className="okr-accordion-arrow" aria-hidden="true">
            {expanded ? "▾" : "▸"}
          </span>
          <span className="okr-objective-title">{objective.title}</span>
          <StatusChip status={objective.status} />
        </div>
        <div className="okr-objective-meta">
          {objective.owner && (
            <span className="okr-owner">Owner: {objective.owner}</span>
          )}
          {objective.due_date && (
            <span className="okr-due-date">
              Due: {new Date(objective.due_date).toLocaleDateString()}
            </span>
          )}
        </div>
        <ProgressBar value={objective.progress} className="okr-objective-progress" />
      </button>

      {expanded && (
        <div className="okr-key-results">
          {objective.description && (
            <p className="okr-description">{objective.description}</p>
          )}
          {objective.key_results.length === 0 ? (
            <p className="okr-kr-empty">No key results yet.</p>
          ) : (
            <ul className="okr-kr-list" aria-label="Key results">
              {objective.key_results.map((kr) => (
                <li key={kr.kr_id} className="okr-kr-item">
                  <div className="okr-kr-title-row">
                    <span className="okr-kr-title">{kr.title}</span>
                    <span className="okr-kr-values">
                      {kr.current_value.toLocaleString()} / {kr.target_value.toLocaleString()} {kr.unit}
                    </span>
                  </div>
                  <ProgressBar value={kr.progress} className="okr-kr-progress" />
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </li>
  );
}

export default function OKRsPage() {
  const [objectives, setObjectives] = useState<Objective[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<NewObjectiveForm>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");

  useEffect(() => {
    fetch(`${BACKEND}/okrs`)
      .then((r) => r.json())
      .then((data: unknown) => {
        setObjectives(Array.isArray(data) ? (data as Objective[]) : []);
      })
      .catch(() => setObjectives([]))
      .finally(() => setLoading(false));
  }, []);

  const handleFormChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError("");
    if (!form.title.trim()) {
      setFormError("Title is required.");
      return;
    }
    setSaving(true);
    try {
      const res = await fetch(`${BACKEND}/okrs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: form.title.trim(),
          description: form.description.trim(),
          owner: form.owner.trim(),
          due_date: form.due_date || undefined,
        }),
      });
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { detail?: string };
        setFormError(err.detail ?? "Failed to create objective.");
        return;
      }
      const created = (await res.json()) as Objective;
      setObjectives((prev) => [created, ...prev]);
      setForm(EMPTY_FORM);
      setShowForm(false);
    } catch {
      setFormError("Network error. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="okr-page">
      <header className="okr-header">
        <div>
          <h1>OKRs</h1>
          <p className="okr-subtitle">Objectives &amp; Key Results</p>
        </div>
        <button className="okr-new-btn" onClick={() => setShowForm((prev) => !prev)}>
          {showForm ? "Cancel" : "+ New Objective"}
        </button>
      </header>

      <div className="okr-period-bar" aria-label="Period">
        <span className="okr-period-label">Current Period</span>
      </div>

      {showForm && (
        <div className="okr-form-container">
          <h2 className="okr-form-title">New Objective</h2>
          <form onSubmit={handleSubmit} className="okr-form">
            <label className="okr-form-label">
              Title
              <input
                className="okr-form-input"
                name="title"
                value={form.title}
                onChange={handleFormChange}
                placeholder="e.g. Grow revenue to $5M ARR"
                required
              />
            </label>
            <label className="okr-form-label">
              Description
              <textarea
                className="okr-form-input okr-form-textarea"
                name="description"
                value={form.description}
                onChange={handleFormChange}
                placeholder="Optional context or rationale"
                rows={3}
              />
            </label>
            <label className="okr-form-label">
              Owner
              <input
                className="okr-form-input"
                name="owner"
                value={form.owner}
                onChange={handleFormChange}
                placeholder="e.g. CEO, Revenue Team"
              />
            </label>
            <label className="okr-form-label">
              Due Date
              <input
                className="okr-form-input"
                name="due_date"
                type="date"
                value={form.due_date}
                onChange={handleFormChange}
              />
            </label>
            {formError && (
              <p className="okr-form-error" role="alert">
                {formError}
              </p>
            )}
            <div className="okr-form-actions">
              <button
                type="button"
                className="okr-form-cancel"
                onClick={() => { setShowForm(false); setFormError(""); setForm(EMPTY_FORM); }}
              >
                Cancel
              </button>
              <button type="submit" className="okr-form-submit" disabled={saving}>
                {saving ? "Creating…" : "Create Objective"}
              </button>
            </div>
          </form>
        </div>
      )}

      {loading ? (
        <p className="okr-empty">Loading…</p>
      ) : objectives.length === 0 ? (
        <div className="okr-empty">
          <p>No OKRs defined yet.</p>
          <p>Click &ldquo;+ New Objective&rdquo; to add one, or ask Friday to create your OKRs.</p>
          <Link href="/">Go to chat →</Link>
        </div>
      ) : (
        <ul className="okr-objectives-list" aria-label="Objectives">
          {objectives.map((obj) => (
            <ObjectiveRow key={obj.objective_id} objective={obj} />
          ))}
        </ul>
      )}
    </main>
  );
}
