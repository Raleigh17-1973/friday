"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageShell } from "@/components/page-shell";

const BACKEND =
  process.env.NEXT_PUBLIC_FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000";

// ── Types ────────────────────────────────────────────────────────────────────

type Objective = {
  obj_id: string;
  title: string;
  description: string;
  owner: string;
  level: "company" | "team" | "individual";
  parent_id: string | null;
  period: string;
  status: string;
  confidence: number;
  progress: number;
  rationale: string;
  collaborators: string[];
  created_at: string;
  workspace_id: string | null;
};

type KeyResult = {
  kr_id: string;
  objective_id: string;
  title: string;
  metric_type: "percentage" | "number" | "currency" | "boolean";
  baseline: number;
  current_value: number;
  target_value: number;
  unit: string;
  owner: string;
  status: string;
  confidence: number;
  due_date: string;
  notes: string;
};

type NewObjectiveForm = {
  title: string;
  level: "company" | "team" | "individual";
  owner: string;
  period: string;
  description: string;
  rationale: string;
};

// ── Helpers ──────────────────────────────────────────────────────────────────

function currentQuarter(): string {
  const d = new Date();
  const q = Math.ceil((d.getMonth() + 1) / 3);
  return `${d.getFullYear()}-Q${q}`;
}

function statusBadgeClass(status: string): string {
  switch (status) {
    case "on_track":
      return "badge-success";
    case "at_risk":
      return "badge-warning";
    case "behind":
      return "badge-danger";
    case "completed":
    case "cancelled":
      return "badge-neutral";
    case "active":
      return "badge-info";
    default:
      return "badge-neutral";
  }
}

function levelColor(level: string): string {
  switch (level) {
    case "company":
      return "#0f5cc0";
    case "team":
      return "#7c3aed";
    case "individual":
      return "#059669";
    default:
      return "#4e657a";
  }
}

function metricIcon(metricType: string): string {
  switch (metricType) {
    case "currency":
      return "💲";
    case "percentage":
      return "%";
    case "boolean":
      return "✓";
    default:
      return "📊";
  }
}

function krProgressColor(status: string, pct: number): string {
  if (status === "on_track" || pct >= 0.7) return "#0f5cc0";
  if (status === "at_risk" || pct >= 0.4) return "#b45309";
  return "#a6332a";
}

// ── Sub-components ────────────────────────────────────────────────────────────

function ProgressBar({
  value,
  color,
  height = 6,
}: {
  value: number;
  color?: string;
  height?: number;
}) {
  const pct = Math.min(100, Math.max(0, Math.round(value * 100)));
  const barColor =
    color ??
    (pct >= 70 ? "var(--success)" : pct >= 40 ? "#b45309" : "var(--danger)");
  return (
    <div
      style={{
        height,
        background: "var(--surface-2)",
        borderRadius: 4,
        overflow: "hidden",
        flex: 1,
      }}
      aria-label={`${pct}%`}
    >
      <div
        style={{
          width: `${pct}%`,
          height: "100%",
          background: barColor,
          borderRadius: 4,
          transition: "width 0.3s",
        }}
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
      />
    </div>
  );
}

function Badge({ label, cls }: { label: string; cls: string }) {
  const styles: Record<string, React.CSSProperties> = {
    "badge-success": {
      background: "#d1fae5",
      color: "#065f46",
      border: "1px solid #6ee7b7",
    },
    "badge-warning": {
      background: "#fef3c7",
      color: "#92400e",
      border: "1px solid #fcd34d",
    },
    "badge-danger": {
      background: "#fee2e2",
      color: "#991b1b",
      border: "1px solid #fca5a5",
    },
    "badge-neutral": {
      background: "var(--surface-2)",
      color: "var(--muted)",
      border: "1px solid var(--line)",
    },
    "badge-info": {
      background: "#dbeafe",
      color: "#1e40af",
      border: "1px solid #93c5fd",
    },
  };
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "2px 10px",
        borderRadius: 999,
        fontSize: "0.72rem",
        fontWeight: 600,
        textTransform: "capitalize",
        whiteSpace: "nowrap",
        ...(styles[cls] ?? styles["badge-neutral"]),
      }}
    >
      {label.replace(/_/g, " ")}
    </span>
  );
}

function StatCard({
  label,
  value,
  badgeCls,
}: {
  label: string;
  value: number;
  badgeCls?: string;
}) {
  return (
    <div className="stat-card">
      <div className="stat-card-value">
        {value}
        {badgeCls && (
          <span style={{ marginLeft: 6 }}>
            <Badge label="" cls={badgeCls} />
          </span>
        )}
      </div>
      <div className="stat-card-label">{label}</div>
    </div>
  );
}

function SkeletonRow() {
  return (
    <div
      style={{
        height: 64,
        borderRadius: 10,
        background: "var(--surface-2)",
        marginBottom: 8,
        animation: "pulse 1.4s ease-in-out infinite",
      }}
    />
  );
}

function KRRow({ kr }: { kr: KeyResult }) {
  const range = kr.target_value - kr.baseline;
  const progress = range === 0 ? 0 : (kr.current_value - kr.baseline) / range;
  const pct = Math.min(1, Math.max(0, progress));
  const barColor = krProgressColor(kr.status, pct);

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "8px 12px",
        background: "var(--surface-2)",
        borderRadius: 8,
        fontSize: "0.84rem",
      }}
    >
      <span style={{ fontSize: "1rem", flexShrink: 0 }}>
        {metricIcon(kr.metric_type)}
      </span>
      <span style={{ flex: 1, fontWeight: 500, minWidth: 0 }}>{kr.title}</span>
      <span style={{ color: "var(--muted)", whiteSpace: "nowrap", fontSize: "0.78rem" }}>
        {kr.baseline.toLocaleString()} → {kr.current_value.toLocaleString()} /{" "}
        {kr.target_value.toLocaleString()} {kr.unit}
      </span>
      <div style={{ width: 80, flexShrink: 0 }}>
        <ProgressBar value={pct} color={barColor} height={5} />
      </div>
      {kr.due_date && (
        <span style={{ color: "var(--muted)", fontSize: "0.72rem", whiteSpace: "nowrap" }}>
          Due {new Date(kr.due_date).toLocaleDateString()}
        </span>
      )}
    </div>
  );
}

function ObjectiveRow({
  objective,
  keyResults,
  allObjectives,
  level,
}: {
  objective: Objective;
  keyResults: Record<string, KeyResult[]>;
  allObjectives: Objective[];
  level: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const children = allObjectives.filter(
    (o) => o.parent_id === objective.obj_id
  );
  const krs = keyResults[objective.obj_id] ?? [];
  const hasContent = children.length > 0 || krs.length > 0;
  const pct = Math.round(objective.progress * 100);
  const confidencePct = Math.round(objective.confidence * 100);

  return (
    <>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "10px 14px",
          paddingLeft: `${14 + level * 28}px`,
          borderBottom: "1px solid var(--line)",
          background: level > 0 ? "var(--surface-2)" : "var(--surface)",
        }}
      >
        {/* Expand toggle */}
        <button
          onClick={() => setExpanded((p) => !p)}
          disabled={!hasContent}
          aria-expanded={expanded}
          style={{
            background: "none",
            border: "none",
            cursor: hasContent ? "pointer" : "default",
            color: hasContent ? "var(--text)" : "transparent",
            fontSize: "0.78rem",
            padding: "0 2px",
            flexShrink: 0,
            width: 16,
          }}
          aria-label={expanded ? "Collapse" : "Expand"}
        >
          {hasContent ? (expanded ? "▼" : "▶") : ""}
        </button>

        {/* Level dot */}
        <span
          style={{
            width: 10,
            height: 10,
            borderRadius: "50%",
            background: levelColor(objective.level),
            flexShrink: 0,
          }}
          title={objective.level}
        />

        {/* Title — links to detail */}
        <Link
          href={`/okrs/${objective.obj_id}`}
          style={{
            fontWeight: 600,
            fontSize: "0.9rem",
            flex: 1,
            minWidth: 0,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            color: "var(--text)",
            textDecoration: "none",
          }}
          onMouseOver={(e) =>
            ((e.target as HTMLElement).style.textDecoration = "underline")
          }
          onMouseOut={(e) =>
            ((e.target as HTMLElement).style.textDecoration = "none")
          }
        >
          {objective.title}
        </Link>

        {/* Owner */}
        {objective.owner && (
          <span
            style={{
              color: "var(--muted)",
              fontSize: "0.78rem",
              whiteSpace: "nowrap",
              flexShrink: 0,
            }}
          >
            {objective.owner}
          </span>
        )}

        {/* Status badge */}
        <Badge
          label={objective.status}
          cls={statusBadgeClass(objective.status)}
        />

        {/* Confidence */}
        <span
          style={{
            fontSize: "0.72rem",
            color: "var(--muted)",
            whiteSpace: "nowrap",
            flexShrink: 0,
          }}
          title={`Confidence: ${confidencePct}%`}
        >
          {confidencePct}%
        </span>

        {/* Progress bar */}
        <div
          style={{ width: 100, flexShrink: 0, display: "flex", alignItems: "center", gap: 6 }}
        >
          <ProgressBar value={objective.progress} height={6} />
          <span style={{ fontSize: "0.72rem", color: "var(--muted)", whiteSpace: "nowrap" }}>
            {pct}%
          </span>
        </div>
      </div>

      {/* Inline KRs when expanded */}
      {expanded && krs.length > 0 && (
        <div
          style={{
            paddingLeft: `${14 + level * 28 + 28}px`,
            paddingRight: 14,
            paddingTop: 8,
            paddingBottom: 8,
            background: "var(--surface-2)",
            borderBottom: "1px solid var(--line)",
            display: "flex",
            flexDirection: "column",
            gap: 6,
          }}
        >
          {krs.map((kr) => (
            <KRRow key={kr.kr_id} kr={kr} />
          ))}
        </div>
      )}

      {/* Child objectives */}
      {expanded &&
        children.map((child) => (
          <ObjectiveRow
            key={child.obj_id}
            objective={child}
            keyResults={keyResults}
            allObjectives={allObjectives}
            level={level + 1}
          />
        ))}
    </>
  );
}

// ── Modal ────────────────────────────────────────────────────────────────────

const EMPTY_FORM: NewObjectiveForm = {
  title: "",
  level: "team",
  owner: "",
  period: currentQuarter(),
  description: "",
  rationale: "",
};

function NewObjectiveModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (obj: Objective) => void;
}) {
  const [form, setForm] = useState<NewObjectiveForm>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const handleChange = (
    e: React.ChangeEvent<
      HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
    >
  ) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!form.title.trim()) {
      setError("Title is required.");
      return;
    }
    setSaving(true);
    try {
      const res = await fetch(`${BACKEND}/okrs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: form.title.trim(),
          level: form.level,
          owner: form.owner.trim(),
          period: form.period.trim() || currentQuarter(),
          description: form.description.trim(),
          rationale: form.rationale.trim(),
        }),
      });
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as {
          detail?: string;
        };
        setError(err.detail ?? "Failed to create objective.");
        return;
      }
      const created = (await res.json()) as Objective;
      onCreated(created);
      onClose();
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.45)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 200,
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          background: "var(--surface)",
          borderRadius: 16,
          padding: 28,
          width: "100%",
          maxWidth: 500,
          boxShadow: "0 8px 32px rgba(15,32,49,0.18)",
        }}
      >
        <h2 style={{ margin: "0 0 20px", fontSize: "1.2rem", fontWeight: 700 }}>
          New Objective
        </h2>
        <form
          onSubmit={handleSubmit}
          style={{ display: "flex", flexDirection: "column", gap: 14 }}
        >
          <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: "0.85rem", fontWeight: 600 }}>
            Title <span style={{ color: "var(--danger)" }}>*</span>
            <input
              name="title"
              value={form.title}
              onChange={handleChange}
              placeholder="e.g. Grow revenue to $5M ARR"
              required
              style={{
                padding: "8px 12px",
                border: "1px solid var(--line)",
                borderRadius: 10,
                fontSize: "0.9rem",
                fontFamily: "inherit",
                color: "var(--text)",
                background: "var(--surface-2)",
              }}
            />
          </label>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: "0.85rem", fontWeight: 600 }}>
              Level
              <select
                name="level"
                value={form.level}
                onChange={handleChange}
                style={{
                  padding: "8px 12px",
                  border: "1px solid var(--line)",
                  borderRadius: 10,
                  fontSize: "0.9rem",
                  fontFamily: "inherit",
                  color: "var(--text)",
                  background: "var(--surface-2)",
                }}
              >
                <option value="company">Company</option>
                <option value="team">Team</option>
                <option value="individual">Individual</option>
              </select>
            </label>

            <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: "0.85rem", fontWeight: 600 }}>
              Period
              <input
                name="period"
                value={form.period}
                onChange={handleChange}
                placeholder="e.g. 2026-Q1"
                style={{
                  padding: "8px 12px",
                  border: "1px solid var(--line)",
                  borderRadius: 10,
                  fontSize: "0.9rem",
                  fontFamily: "inherit",
                  color: "var(--text)",
                  background: "var(--surface-2)",
                }}
              />
            </label>
          </div>

          <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: "0.85rem", fontWeight: 600 }}>
            Owner
            <input
              name="owner"
              value={form.owner}
              onChange={handleChange}
              placeholder="e.g. CEO, Revenue Team"
              style={{
                padding: "8px 12px",
                border: "1px solid var(--line)",
                borderRadius: 10,
                fontSize: "0.9rem",
                fontFamily: "inherit",
                color: "var(--text)",
                background: "var(--surface-2)",
              }}
            />
          </label>

          <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: "0.85rem", fontWeight: 600 }}>
            Description
            <textarea
              name="description"
              value={form.description}
              onChange={handleChange}
              placeholder="Optional context"
              rows={2}
              style={{
                padding: "8px 12px",
                border: "1px solid var(--line)",
                borderRadius: 10,
                fontSize: "0.9rem",
                fontFamily: "inherit",
                color: "var(--text)",
                background: "var(--surface-2)",
                resize: "vertical",
              }}
            />
          </label>

          <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: "0.85rem", fontWeight: 600 }}>
            Rationale
            <textarea
              name="rationale"
              value={form.rationale}
              onChange={handleChange}
              placeholder="Why does this matter?"
              rows={2}
              style={{
                padding: "8px 12px",
                border: "1px solid var(--line)",
                borderRadius: 10,
                fontSize: "0.9rem",
                fontFamily: "inherit",
                color: "var(--text)",
                background: "var(--surface-2)",
                resize: "vertical",
              }}
            />
          </label>

          {error && (
            <p
              role="alert"
              style={{ color: "var(--danger)", fontSize: "0.82rem", margin: 0 }}
            >
              {error}
            </p>
          )}

          <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 4 }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                minHeight: 40,
                padding: "0 16px",
                borderRadius: 999,
                border: "1px solid var(--line)",
                background: "var(--surface)",
                cursor: "pointer",
                fontSize: "0.88rem",
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="btn btn-primary"
              style={{
                minHeight: 40,
                padding: "0 20px",
                borderRadius: 999,
                border: "none",
                background: "var(--accent)",
                color: "#fff",
                cursor: saving ? "not-allowed" : "pointer",
                fontSize: "0.88rem",
                fontWeight: 600,
                opacity: saving ? 0.7 : 1,
              }}
            >
              {saving ? "Creating…" : "Create Objective"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────────

export default function OKRsPage() {
  const [objectives, setObjectives] = useState<Objective[]>([]);
  const [keyResults, setKeyResults] = useState<Record<string, KeyResult[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showModal, setShowModal] = useState(false);

  const [period, setPeriod] = useState(currentQuarter());
  const [levelFilter, setLevelFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  // Fetch all objectives
  useEffect(() => {
    setLoading(true);
    setError("");
    const params = new URLSearchParams();
    if (period) params.set("period", period);
    if (levelFilter !== "all") params.set("level", levelFilter);
    if (statusFilter !== "all") params.set("status", statusFilter);

    fetch(`${BACKEND}/okrs?${params}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data: unknown) => {
        const list = Array.isArray(data) ? (data as Objective[]) : [];
        setObjectives(list);
        // Fetch KRs for each objective in parallel
        return Promise.all(
          list.map((obj) =>
            fetch(`${BACKEND}/okrs/${obj.obj_id}`)
              .then((r) => (r.ok ? r.json() : null))
              .then((detail) => ({
                obj_id: obj.obj_id,
                krs: (detail?.key_results ?? []) as KeyResult[],
              }))
              .catch(() => ({ obj_id: obj.obj_id, krs: [] }))
          )
        );
      })
      .then((results) => {
        const krMap: Record<string, KeyResult[]> = {};
        for (const r of results) {
          krMap[r.obj_id] = r.krs;
        }
        setKeyResults(krMap);
      })
      .catch((e: Error) => setError(e.message || "Failed to load objectives."))
      .finally(() => setLoading(false));
  }, [period, levelFilter, statusFilter]);

  // Computed stats
  const total = objectives.length;
  const onTrack = objectives.filter((o) => o.status === "on_track").length;
  const atRisk = objectives.filter((o) => o.status === "at_risk").length;
  const behind = objectives.filter((o) => o.status === "behind").length;

  // Build hierarchy — only top-level (no parent) at root
  const topLevel = objectives.filter((o) => !o.parent_id);

  const handleCreated = (obj: Objective) => {
    setObjectives((prev) => [obj, ...prev]);
  };

  return (
    <PageShell title="OKRs">
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.4; }
        }
        .stat-card-row {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 12px;
          margin-bottom: 24px;
        }
        .stat-card {
          background: var(--surface);
          border: 1px solid var(--line);
          border-radius: 12px;
          padding: 16px 20px;
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        .stat-card-value {
          font-size: 2rem;
          font-weight: 700;
          line-height: 1;
          display: flex;
          align-items: center;
        }
        .stat-card-label {
          font-size: 0.78rem;
          color: var(--muted);
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }
        .empty-state {
          text-align: center;
          padding: 60px 20px;
          color: var(--muted);
        }
        .empty-state-icon {
          font-size: 3rem;
          margin-bottom: 12px;
        }
        .empty-state h2 {
          font-size: 1.2rem;
          margin: 0 0 8px;
          color: var(--text);
        }
        .empty-state p {
          margin: 0 0 20px;
          font-size: 0.9rem;
        }
        .btn.btn-primary {
          display: inline-flex;
          align-items: center;
          min-height: 40px;
          padding: 0 20px;
          border-radius: 999px;
          border: none;
          background: var(--accent);
          color: #fff;
          font-size: 0.88rem;
          font-weight: 600;
          cursor: pointer;
          text-decoration: none;
        }
        .btn.btn-primary:hover { background: #0d52b0; }
        @media (max-width: 640px) {
          .stat-card-row { grid-template-columns: repeat(2, 1fr); }
        }
      `}</style>

      {/* Page header */}
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          marginBottom: 24,
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        <div>
          <h1 style={{ margin: "0 0 4px", fontSize: "1.6rem", fontWeight: 700 }}>
            OKRs
          </h1>
          <p style={{ margin: 0, color: "var(--muted)", fontSize: "0.95rem" }}>
            Objectives &amp; Key Results
          </p>
        </div>
        <button
          className="btn btn-primary"
          onClick={() => setShowModal(true)}
        >
          + New Objective
        </button>
      </div>

      {/* Stat cards */}
      <div className="stat-card-row">
        <div className="stat-card">
          <div className="stat-card-value">{total}</div>
          <div className="stat-card-label">Total Objectives</div>
        </div>
        <div className="stat-card">
          <div className="stat-card-value" style={{ color: "#065f46" }}>
            {onTrack}
          </div>
          <div className="stat-card-label" style={{ color: "#065f46" }}>
            On Track
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-card-value" style={{ color: "#92400e" }}>
            {atRisk}
          </div>
          <div className="stat-card-label" style={{ color: "#92400e" }}>
            At Risk
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-card-value" style={{ color: "var(--danger)" }}>
            {behind}
          </div>
          <div className="stat-card-label" style={{ color: "var(--danger)" }}>
            Behind
          </div>
        </div>
      </div>

      {/* Filter bar */}
      <div
        style={{
          display: "flex",
          gap: 10,
          alignItems: "center",
          marginBottom: 20,
          flexWrap: "wrap",
        }}
      >
        <label
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            fontSize: "0.85rem",
          }}
        >
          <span style={{ color: "var(--muted)" }}>Period</span>
          <input
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            placeholder="e.g. 2026-Q1"
            style={{
              padding: "6px 10px",
              border: "1px solid var(--line)",
              borderRadius: 8,
              fontSize: "0.85rem",
              fontFamily: "inherit",
              color: "var(--text)",
              background: "var(--surface)",
              width: 100,
            }}
          />
        </label>

        <label
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            fontSize: "0.85rem",
          }}
        >
          <span style={{ color: "var(--muted)" }}>Level</span>
          <select
            value={levelFilter}
            onChange={(e) => setLevelFilter(e.target.value)}
            style={{
              padding: "6px 10px",
              border: "1px solid var(--line)",
              borderRadius: 8,
              fontSize: "0.85rem",
              fontFamily: "inherit",
              color: "var(--text)",
              background: "var(--surface)",
            }}
          >
            <option value="all">All</option>
            <option value="company">Company</option>
            <option value="team">Team</option>
            <option value="individual">Individual</option>
          </select>
        </label>

        <label
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            fontSize: "0.85rem",
          }}
        >
          <span style={{ color: "var(--muted)" }}>Status</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{
              padding: "6px 10px",
              border: "1px solid var(--line)",
              borderRadius: 8,
              fontSize: "0.85rem",
              fontFamily: "inherit",
              color: "var(--text)",
              background: "var(--surface)",
            }}
          >
            <option value="all">All</option>
            <option value="active">Active</option>
            <option value="on_track">On Track</option>
            <option value="at_risk">At Risk</option>
            <option value="behind">Behind</option>
            <option value="completed">Completed</option>
          </select>
        </label>
      </div>

      {/* Hierarchy tree */}
      {loading ? (
        <div>
          <SkeletonRow />
          <SkeletonRow />
          <SkeletonRow />
        </div>
      ) : error ? (
        <div
          style={{
            padding: "20px 16px",
            background: "#fff6f2",
            border: "1px solid #f5ccbb",
            borderRadius: 10,
            color: "var(--danger)",
          }}
        >
          {error}
        </div>
      ) : objectives.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">🎯</div>
          <h2>No OKRs yet</h2>
          <p>Set your first objective to track what matters most.</p>
          <button
            className="btn btn-primary"
            onClick={() => setShowModal(true)}
          >
            Create First OKR
          </button>
        </div>
      ) : (
        <div
          style={{
            border: "1px solid var(--line)",
            borderRadius: 12,
            overflow: "hidden",
            background: "var(--surface)",
          }}
        >
          {/* Column headers */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "8px 14px",
              background: "var(--surface-2)",
              borderBottom: "1px solid var(--line)",
              fontSize: "0.72rem",
              color: "var(--muted)",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              fontWeight: 600,
            }}
          >
            <span style={{ width: 16, flexShrink: 0 }} />
            <span style={{ width: 10, flexShrink: 0 }} />
            <span style={{ flex: 1 }}>Objective</span>
            <span style={{ width: 80 }}>Owner</span>
            <span style={{ width: 80 }}>Status</span>
            <span style={{ width: 40, textAlign: "right" }}>Conf.</span>
            <span style={{ width: 120 }}>Progress</span>
          </div>

          {topLevel.map((obj) => (
            <ObjectiveRow
              key={obj.obj_id}
              objective={obj}
              keyResults={keyResults}
              allObjectives={objectives}
              level={0}
            />
          ))}
        </div>
      )}

      {/* New Objective Modal */}
      {showModal && (
        <NewObjectiveModal
          onClose={() => setShowModal(false)}
          onCreated={handleCreated}
        />
      )}
    </PageShell>
  );
}
