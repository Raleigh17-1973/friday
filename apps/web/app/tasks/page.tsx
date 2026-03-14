"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageShell } from "@/components/page-shell";

const BACKEND = process.env.NEXT_PUBLIC_FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000";

type Task = {
  task_id: string;
  title: string;
  description: string;
  assignee: string | null;
  due_date: string | null;
  priority: "low" | "medium" | "high" | "urgent";
  status: "open" | "in_progress" | "done" | "cancelled";
  workspace_id: string | null;
  okr_id: string | null;
  kr_id: string | null;
  process_id: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
};

const PRIORITY_COLORS: Record<string, string> = {
  urgent: "var(--danger)",
  high:   "#d97706",
  medium: "var(--text-muted)",
  low:    "#6b7280",
};

const PRIORITY_LABELS: Record<string, string> = {
  urgent: "Urgent",
  high:   "High",
  medium: "Medium",
  low:    "Low",
};

const STATUS_LABELS: Record<string, string> = {
  open:        "Open",
  in_progress: "In Progress",
  done:        "Done",
  cancelled:   "Cancelled",
};

function PriorityDot({ priority }: { priority: string }) {
  return (
    <span
      style={{
        display: "inline-block",
        width: "8px",
        height: "8px",
        borderRadius: "50%",
        background: PRIORITY_COLORS[priority] ?? "var(--text-muted)",
        flexShrink: 0,
      }}
      title={PRIORITY_LABELS[priority] ?? priority}
    />
  );
}

function StatusChip({ status }: { status: string }) {
  return <span className={`status-chip status-${status.replace("_", "-")}`}>{STATUS_LABELS[status] ?? status}</span>;
}

function DueDateLabel({ dueDate }: { dueDate: string | null }) {
  if (!dueDate) return null;
  const d = new Date(dueDate);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = Math.ceil((d.getTime() - today.getTime()) / 86400000);
  const color = diff < 0 ? "var(--danger)" : diff <= 2 ? "#d97706" : "var(--text-muted)";
  const label = diff < 0 ? `${Math.abs(diff)}d overdue` : diff === 0 ? "Today" : diff === 1 ? "Tomorrow" : `${diff}d`;
  return <span style={{ fontSize: "0.75rem", color }}>{label}</span>;
}

type StatusFilter = "all" | "open" | "in_progress" | "done" | "cancelled";

interface NewTaskForm {
  title: string;
  description: string;
  assignee: string;
  due_date: string;
  priority: string;
  workspace_id: string;
  okr_id: string;
}

const BLANK_FORM: NewTaskForm = {
  title: "",
  description: "",
  assignee: "",
  due_date: "",
  priority: "medium",
  workspace_id: "",
  okr_id: "",
};

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("open");
  const [showNewForm, setShowNewForm] = useState(false);
  const [form, setForm] = useState<NewTaskForm>(BLANK_FORM);
  const [saving, setSaving] = useState(false);
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const loadTasks = () => {
    setLoading(true);
    const qs = statusFilter !== "all" ? `?status=${statusFilter}` : "";
    fetch(`${BACKEND}/tasks${qs}`)
      .then((r) => r.json())
      .then((data: unknown) => setTasks(Array.isArray(data) ? (data as Task[]) : []))
      .catch(() => setTasks([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadTasks();
  }, [statusFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.title.trim()) return;
    setSaving(true);
    try {
      const body: Record<string, unknown> = {
        title: form.title.trim(),
        priority: form.priority,
      };
      if (form.description.trim()) body.description = form.description.trim();
      if (form.assignee.trim()) body.assignee = form.assignee.trim();
      if (form.due_date) body.due_date = form.due_date;
      if (form.workspace_id.trim()) body.workspace_id = form.workspace_id.trim();
      if (form.okr_id.trim()) body.okr_id = form.okr_id.trim();

      await fetch(`${BACKEND}/tasks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      setForm(BLANK_FORM);
      setShowNewForm(false);
      loadTasks();
    } catch {
      /* ignore */
    } finally {
      setSaving(false);
    }
  };

  const cycleStatus = async (task: Task) => {
    const cycle: Task["status"][] = ["open", "in_progress", "done"];
    const idx = cycle.indexOf(task.status);
    if (idx === -1) return;
    const next = cycle[(idx + 1) % cycle.length];
    setUpdatingId(task.task_id);
    try {
      await fetch(`${BACKEND}/tasks/${task.task_id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: next }),
      });
      setTasks((prev) => prev.map((t) => (t.task_id === task.task_id ? { ...t, status: next } : t)));
    } catch {
      /* ignore */
    } finally {
      setUpdatingId(null);
    }
  };

  const countsByStatus: Record<string, number> = { open: 0, in_progress: 0, done: 0, cancelled: 0 };
  tasks.forEach((t) => { if (countsByStatus[t.status] !== undefined) countsByStatus[t.status]++; });

  const allTasks = [...tasks];
  const displayed =
    statusFilter === "all" ? allTasks : allTasks.filter((t) => t.status === statusFilter);

  // Group open/in_progress tasks together; done and cancelled separate
  const groups: { label: string; status: StatusFilter; tasks: Task[] }[] =
    statusFilter === "all"
      ? (
          [
            { label: "Open",        status: "open" as StatusFilter,        tasks: tasks.filter((t) => t.status === "open")        },
            { label: "In Progress", status: "in_progress" as StatusFilter, tasks: tasks.filter((t) => t.status === "in_progress") },
            { label: "Done",        status: "done" as StatusFilter,        tasks: tasks.filter((t) => t.status === "done")        },
            { label: "Cancelled",   status: "cancelled" as StatusFilter,   tasks: tasks.filter((t) => t.status === "cancelled")   },
          ] as { label: string; status: StatusFilter; tasks: Task[] }[]
        ).filter((g) => g.tasks.length > 0)
      : [{ label: STATUS_LABELS[statusFilter] ?? statusFilter, status: statusFilter, tasks: displayed }];

  return (
    <PageShell
      title="Tasks"
      subtitle="Track work items linked to OKRs, processes, and workspaces"
      headerActions={
        <button className="btn btn-primary" onClick={() => setShowNewForm((v) => !v)}>
          {showNewForm ? "Cancel" : "+ New Task"}
        </button>
      }
    >
      {/* Summary stat row */}
      <div className="stat-card-row">
        <div className="stat-card">
          <div className="stat-card-label">Open</div>
          <div className="stat-card-value">{countsByStatus.open}</div>
        </div>
        <div className="stat-card">
          <div className="stat-card-label">In Progress</div>
          <div className="stat-card-value" style={{ color: "#d97706" }}>{countsByStatus.in_progress}</div>
        </div>
        <div className="stat-card">
          <div className="stat-card-label">Done</div>
          <div className="stat-card-value" style={{ color: "var(--success)" }}>{countsByStatus.done}</div>
        </div>
        <div className="stat-card">
          <div className="stat-card-label">Cancelled</div>
          <div className="stat-card-value" style={{ color: "var(--text-muted)" }}>{countsByStatus.cancelled}</div>
        </div>
      </div>

      {/* New task form */}
      {showNewForm && (
        <form onSubmit={handleCreate} className="card" style={{ marginBottom: "1.5rem" }}>
          <div className="card-header">
            <span style={{ fontWeight: 600 }}>New Task</span>
          </div>
          <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            <input
              className="form-input"
              placeholder="Task title *"
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              required
              autoFocus
            />
            <textarea
              className="form-input"
              placeholder="Description (optional)"
              rows={2}
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              style={{ resize: "vertical" }}
            />
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.75rem" }}>
              <input
                className="form-input"
                placeholder="Assignee"
                value={form.assignee}
                onChange={(e) => setForm((f) => ({ ...f, assignee: e.target.value }))}
              />
              <input
                className="form-input"
                type="date"
                value={form.due_date}
                onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))}
                title="Due date"
              />
              <select
                className="form-input"
                value={form.priority}
                onChange={(e) => setForm((f) => ({ ...f, priority: e.target.value }))}
              >
                <option value="urgent">Urgent</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
              <input
                className="form-input"
                placeholder="Workspace ID (optional)"
                value={form.workspace_id}
                onChange={(e) => setForm((f) => ({ ...f, workspace_id: e.target.value }))}
              />
              <input
                className="form-input"
                placeholder="OKR ID (optional)"
                value={form.okr_id}
                onChange={(e) => setForm((f) => ({ ...f, okr_id: e.target.value }))}
              />
            </div>
            <div style={{ display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => { setShowNewForm(false); setForm(BLANK_FORM); }}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary btn-sm" disabled={saving || !form.title.trim()}>
                {saving ? "Saving…" : "Create Task"}
              </button>
            </div>
          </div>
        </form>
      )}

      {/* Status filter pills */}
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1.25rem" }} role="group" aria-label="Filter by status">
        {(["all", "open", "in_progress", "done", "cancelled"] as const).map((s) => (
          <button
            key={s}
            className={`btn ${statusFilter === s ? "btn-primary" : "btn-secondary"} btn-sm`}
            onClick={() => setStatusFilter(s)}
          >
            {STATUS_LABELS[s] ?? "All"}
          </button>
        ))}
      </div>

      {/* Task list */}
      {loading ? (
        <div className="loading-skeleton">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="loading-skeleton-row" style={{ height: "3.5rem", borderRadius: "0.5rem" }} />
          ))}
        </div>
      ) : groups.length === 0 || groups.every((g) => g.tasks.length === 0) ? (
        <div className="empty-state">
          <div className="empty-state-icon">✓</div>
          <p className="empty-state-title">No tasks here</p>
          <p className="empty-state-body">
            {statusFilter === "open"
              ? "You're all caught up! Create a task or ask Friday to create one for you."
              : "No tasks in this status."}
          </p>
          <button className="btn btn-primary" onClick={() => setShowNewForm(true)}>Create Task</button>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          {groups.map((group) => (
            <section key={group.status}>
              {statusFilter === "all" && (
                <h2 style={{ fontSize: "0.8125rem", fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.5rem" }}>
                  {group.label} · {group.tasks.length}
                </h2>
              )}
              <ul style={{ listStyle: "none", padding: 0, display: "flex", flexDirection: "column", gap: "0.375rem" }}>
                {group.tasks.map((task) => (
                  <li key={task.task_id} className="card" style={{ padding: "0.75rem 1rem" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                      {/* Status toggle button */}
                      <button
                        onClick={() => cycleStatus(task)}
                        disabled={updatingId === task.task_id || task.status === "cancelled"}
                        title={`Click to advance status (currently ${STATUS_LABELS[task.status]})`}
                        style={{
                          width: "20px",
                          height: "20px",
                          borderRadius: "50%",
                          border: `2px solid ${task.status === "done" ? "var(--success)" : task.status === "in_progress" ? "#d97706" : "var(--border)"}`,
                          background: task.status === "done" ? "var(--success)" : "transparent",
                          cursor: task.status === "cancelled" ? "default" : "pointer",
                          flexShrink: 0,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          fontSize: "0.625rem",
                          color: "white",
                          padding: 0,
                        }}
                      >
                        {task.status === "done" && "✓"}
                        {task.status === "in_progress" && "→"}
                      </button>

                      {/* Priority dot */}
                      <PriorityDot priority={task.priority} />

                      {/* Title + description */}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <span
                          style={{
                            fontWeight: 500,
                            fontSize: "0.9375rem",
                            color: task.status === "done" ? "var(--text-muted)" : "var(--text)",
                            textDecoration: task.status === "done" ? "line-through" : "none",
                          }}
                        >
                          {task.title}
                        </span>
                        {task.description && (
                          <p style={{ fontSize: "0.8125rem", color: "var(--text-muted)", margin: "0.125rem 0 0", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {task.description}
                          </p>
                        )}
                      </div>

                      {/* Meta: assignee, due date, links */}
                      <div style={{ display: "flex", alignItems: "center", gap: "0.625rem", flexShrink: 0 }}>
                        {task.assignee && (
                          <span style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>@{task.assignee}</span>
                        )}
                        <DueDateLabel dueDate={task.due_date} />
                        {task.okr_id && (
                          <Link
                            href={`/okrs/${task.okr_id}`}
                            style={{ fontSize: "0.75rem", color: "var(--accent)", textDecoration: "none" }}
                            title="Linked OKR"
                          >
                            OKR ↗
                          </Link>
                        )}
                        {task.process_id && (
                          <Link
                            href={`/processes/${task.process_id}`}
                            style={{ fontSize: "0.75rem", color: "var(--accent)", textDecoration: "none" }}
                            title="Linked Process"
                          >
                            Process ↗
                          </Link>
                        )}
                        <StatusChip status={task.status} />
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}

      {/* Ask Friday shortcut */}
      <div style={{ marginTop: "2rem", paddingTop: "1.25rem", borderTop: "1px solid var(--border)", textAlign: "center" }}>
        <p style={{ fontSize: "0.875rem", color: "var(--text-muted)" }}>
          Ask Friday to create tasks:{" "}
          <Link href="/" style={{ color: "var(--accent)" }}>"Create a task to follow up with Acme by Friday"</Link>
        </p>
      </div>
    </PageShell>
  );
}
