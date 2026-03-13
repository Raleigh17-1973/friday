"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageShell } from "@/components/page-shell";

const BACKEND = process.env.NEXT_PUBLIC_FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000";

type KPIStatus = "on_track" | "at_risk" | "behind";
type KPIDirection = "higher_is_better" | "lower_is_better";

type KPI = {
  kpi_id: string;
  name: string;
  unit: string;
  target_value: number;
  current_value: number;
  direction: KPIDirection;
  category: string;
  status: KPIStatus;
};

type NewKPIForm = {
  name: string;
  unit: string;
  target_value: string;
  direction: KPIDirection;
  category: string;
};

const STATUS_LABELS: Record<KPIStatus, string> = {
  on_track: "On Track",
  at_risk: "At Risk",
  behind: "Behind",
};

function trendArrow(kpi: KPI): string {
  const delta = kpi.current_value - kpi.target_value;
  if (kpi.direction === "higher_is_better") {
    if (delta >= 0) return "↑";
    return "↓";
  } else {
    if (delta <= 0) return "↑";
    return "↓";
  }
}

function trendClass(kpi: KPI): string {
  if (kpi.status === "on_track") return "analytics-trend-up";
  if (kpi.status === "behind") return "analytics-trend-down";
  return "analytics-trend-neutral";
}

const EMPTY_FORM: NewKPIForm = {
  name: "",
  unit: "",
  target_value: "",
  direction: "higher_is_better",
  category: "",
};

export default function AnalyticsPage() {
  const [kpis, setKpis] = useState<KPI[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState<NewKPIForm>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");

  useEffect(() => {
    fetch(`${BACKEND}/kpis`)
      .then((r) => r.json())
      .then((data: unknown) => {
        setKpis(Array.isArray(data) ? (data as KPI[]) : []);
      })
      .catch(() => setKpis([]))
      .finally(() => setLoading(false));
  }, []);

  const onTrack = kpis.filter((k) => k.status === "on_track").length;
  const atRisk = kpis.filter((k) => k.status === "at_risk").length;
  const behind = kpis.filter((k) => k.status === "behind").length;

  const handleFormChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleAddKPI = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError("");
    if (!form.name.trim() || !form.unit.trim() || !form.target_value) {
      setFormError("Name, unit, and target value are required.");
      return;
    }
    setSaving(true);
    try {
      const res = await fetch(`${BACKEND}/kpis`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: form.name.trim(),
          unit: form.unit.trim(),
          target_value: parseFloat(form.target_value),
          direction: form.direction,
          category: form.category.trim(),
        }),
      });
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { detail?: string };
        setFormError(err.detail ?? "Failed to add KPI.");
        return;
      }
      const created = (await res.json()) as KPI;
      setKpis((prev) => [created, ...prev]);
      setForm(EMPTY_FORM);
      setShowModal(false);
    } catch {
      setFormError("Network error. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <PageShell
      title="Analytics"
      subtitle="KPI tracking and business intelligence"
      headerActions={
        <button className="analytics-add-btn" onClick={() => setShowModal(true)}>
          + Add KPI
        </button>
      }
    >
    <div className="analytics-page">
      {!loading && kpis.length > 0 && (
        <section className="analytics-summary" aria-label="KPI summary">
          <div className="analytics-summary-stat">
            <span className="analytics-summary-num">{kpis.length}</span>
            <span className="analytics-summary-label">Total KPIs</span>
          </div>
          <div className="analytics-summary-stat analytics-stat-on-track">
            <span className="analytics-summary-num">{onTrack}</span>
            <span className="analytics-summary-label">On Track</span>
          </div>
          <div className="analytics-summary-stat analytics-stat-at-risk">
            <span className="analytics-summary-num">{atRisk}</span>
            <span className="analytics-summary-label">At Risk</span>
          </div>
          <div className="analytics-summary-stat analytics-stat-behind">
            <span className="analytics-summary-num">{behind}</span>
            <span className="analytics-summary-label">Behind</span>
          </div>
        </section>
      )}

      {loading ? (
        <p className="analytics-empty">Loading…</p>
      ) : kpis.length === 0 ? (
        <div className="analytics-empty">
          <p>No KPIs defined yet.</p>
          <p>Click &ldquo;+ Add KPI&rdquo; to get started, or ask Friday to track a metric.</p>
          <Link href="/">Go to chat →</Link>
        </div>
      ) : (
        <ul className="analytics-grid" aria-label="KPI list">
          {kpis.map((kpi) => (
            <li key={kpi.kpi_id} className="analytics-card">
              <div className="analytics-card-top">
                <h2 className="analytics-kpi-name">{kpi.name}</h2>
                <span className={`analytics-status-badge analytics-status-${kpi.status}`}>
                  {STATUS_LABELS[kpi.status]}
                </span>
              </div>
              <div className="analytics-kpi-value">
                <span className="analytics-current-value">
                  {kpi.current_value.toLocaleString()}
                  <span className="analytics-unit">{kpi.unit}</span>
                </span>
                <span className={`analytics-trend ${trendClass(kpi)}`} aria-hidden="true">
                  {trendArrow(kpi)}
                </span>
              </div>
              <div className="analytics-kpi-target">
                Target: {kpi.target_value.toLocaleString()} {kpi.unit}
              </div>
              {kpi.category && (
                <span className="analytics-category-tag">{kpi.category}</span>
              )}
            </li>
          ))}
        </ul>
      )}

      {showModal && (
        <div className="analytics-modal-backdrop" role="dialog" aria-modal="true" aria-label="Add KPI">
          <div className="analytics-modal">
            <header className="analytics-modal-header">
              <h2>Add KPI</h2>
              <button
                className="analytics-modal-close"
                onClick={() => { setShowModal(false); setFormError(""); setForm(EMPTY_FORM); }}
                aria-label="Close"
              >
                ✕
              </button>
            </header>
            <form onSubmit={handleAddKPI} className="analytics-form">
              <label className="analytics-form-label">
                Name
                <input
                  className="analytics-form-input"
                  name="name"
                  value={form.name}
                  onChange={handleFormChange}
                  placeholder="e.g. Monthly Recurring Revenue"
                  required
                />
              </label>
              <label className="analytics-form-label">
                Unit
                <input
                  className="analytics-form-input"
                  name="unit"
                  value={form.unit}
                  onChange={handleFormChange}
                  placeholder="e.g. USD, %, customers"
                  required
                />
              </label>
              <label className="analytics-form-label">
                Target Value
                <input
                  className="analytics-form-input"
                  name="target_value"
                  type="number"
                  value={form.target_value}
                  onChange={handleFormChange}
                  placeholder="e.g. 100000"
                  required
                />
              </label>
              <label className="analytics-form-label">
                Direction
                <select
                  className="analytics-form-input"
                  name="direction"
                  value={form.direction}
                  onChange={handleFormChange}
                >
                  <option value="higher_is_better">Higher is better</option>
                  <option value="lower_is_better">Lower is better</option>
                </select>
              </label>
              <label className="analytics-form-label">
                Category
                <input
                  className="analytics-form-input"
                  name="category"
                  value={form.category}
                  onChange={handleFormChange}
                  placeholder="e.g. Revenue, Growth, Operations"
                />
              </label>
              {formError && (
                <p className="analytics-form-error" role="alert">
                  {formError}
                </p>
              )}
              <div className="analytics-form-actions">
                <button
                  type="button"
                  className="analytics-form-cancel"
                  onClick={() => { setShowModal(false); setFormError(""); setForm(EMPTY_FORM); }}
                >
                  Cancel
                </button>
                <button type="submit" className="analytics-form-submit" disabled={saving}>
                  {saving ? "Saving…" : "Add KPI"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
    </PageShell>
  );
}
