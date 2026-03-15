"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageShell } from "@/components/page-shell";

const BACKEND = process.env.NEXT_PUBLIC_FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000";

// ── Types ─────────────────────────────────────────────────────────────────────

type Task = {
  task_id: string;
  title: string;
  assignee: string | null;
  due_date: string | null;
  priority: string;
  status: string;
};

type Approval = {
  request_id: string;
  action_type: string;
  summary: string;
  created_at: string;
  status: string;
};

type Alert = {
  alert_id?: string;
  id?: string;
  title: string;
  body: string;
  severity: "info" | "warning" | "critical";
  created_at: string;
};

type Decision = {
  decision_id: string;
  title: string;
  rationale: string;
  decided_at: string;
  decision_maker: string;
};

type ActivityEntry = {
  activity_id: string;
  action: string;
  entity_type: string;
  entity_id: string;
  entity_title: string;
  actor_id: string;
  metadata: Record<string, string | number | boolean>;
  created_at: string;
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function relTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const h = Math.floor(diff / 3600000);
  if (h < 1) return "just now";
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

function dueDateLabel(dueDate: string | null): { label: string; color: string } | null {
  if (!dueDate) return null;
  const d = new Date(dueDate);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = Math.ceil((d.getTime() - today.getTime()) / 86400000);
  if (diff < 0) return { label: `${Math.abs(diff)}d overdue`, color: "var(--danger)" };
  if (diff === 0) return { label: "Today", color: "#d97706" };
  if (diff === 1) return { label: "Tomorrow", color: "#d97706" };
  return { label: `${diff}d`, color: "var(--text-muted)" };
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: "var(--danger)",
  warning:  "#d97706",
  info:     "var(--accent)",
};

// ── Section card ──────────────────────────────────────────────────────────────

function Section({
  title,
  count,
  children,
  viewAllHref,
  empty,
}: {
  title: string;
  count?: number;
  children: React.ReactNode;
  viewAllHref?: string;
  empty?: boolean;
}) {
  return (
    <div className="card" style={{ marginBottom: "1rem" }}>
      <div className="card-header" style={{ justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <span style={{ fontWeight: 600, fontSize: "0.9375rem" }}>{title}</span>
          {count !== undefined && count > 0 && (
            <span
              style={{
                fontSize: "0.6875rem",
                fontWeight: 600,
                padding: "0.125rem 0.4rem",
                borderRadius: "999px",
                background: "var(--accent)",
                color: "white",
              }}
            >
              {count}
            </span>
          )}
        </div>
        {viewAllHref && !empty && (
          <Link href={viewAllHref} style={{ fontSize: "0.8125rem", color: "var(--accent)", textDecoration: "none" }}>
            View all →
          </Link>
        )}
      </div>
      <div className="card-body">{children}</div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function HomePage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [activity, setActivity] = useState<ActivityEntry[]>([]);
  const [loadingTasks, setLoadingTasks] = useState(true);
  const [loadingApprovals, setLoadingApprovals] = useState(true);
  const [loadingAlerts, setLoadingAlerts] = useState(true);
  const [loadingDecisions, setLoadingDecisions] = useState(true);
  const [loadingActivity, setLoadingActivity] = useState(true);

  const now = new Date();
  const todayIso = now.toISOString().slice(0, 10);
  const in7 = new Date(now.getTime() + 7 * 86400000).toISOString().slice(0, 10);

  useEffect(() => {
    // Tasks due within 7 days or overdue, not done
    fetch(`${BACKEND}/tasks?due_before=${in7}&limit=10`)
      .then((r) => r.json())
      .then((data: unknown) => {
        const all = Array.isArray(data) ? (data as Task[]) : [];
        setTasks(all.filter((t) => t.status !== "done" && t.status !== "cancelled"));
      })
      .catch(() => setTasks([]))
      .finally(() => setLoadingTasks(false));

    fetch(`${BACKEND}/approvals?status=pending`)
      .then((r) => r.json())
      .then((data: unknown) => {
        const d = data as { approvals?: Approval[] };
        setApprovals(d.approvals ?? []);
      })
      .catch(() => setApprovals([]))
      .finally(() => setLoadingApprovals(false));

    fetch(`${BACKEND}/alerts?org_id=org-1`)
      .then((r) => r.json())
      .then((data: unknown) => {
        const d = data as { alerts?: Alert[] };
        setAlerts((d.alerts ?? []).slice(0, 5));
      })
      .catch(() => setAlerts([]))
      .finally(() => setLoadingAlerts(false));

    fetch(`${BACKEND}/decisions?org_id=org-1`)
      .then((r) => r.json())
      .then((data: unknown) => {
        setDecisions(Array.isArray(data) ? (data as Decision[]).slice(0, 5) : []);
      })
      .catch(() => setDecisions([]))
      .finally(() => setLoadingDecisions(false));

    fetch(`${BACKEND}/activity?org_id=org-1&limit=20`)
      .then((r) => r.json())
      .then((data: unknown) => {
        setActivity(Array.isArray(data) ? (data as ActivityEntry[]) : []);
      })
      .catch(() => setActivity([]))
      .finally(() => setLoadingActivity(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleApprove = async (id: string) => {
    await fetch(`${BACKEND}/approvals/${id}/approve`, { method: "POST" }).catch(() => undefined);
    setApprovals((prev) => prev.filter((a) => a.request_id !== id));
  };

  const handleReject = async (id: string) => {
    await fetch(`${BACKEND}/approvals/${id}/reject`, { method: "POST" }).catch(() => undefined);
    setApprovals((prev) => prev.filter((a) => a.request_id !== id));
  };

  const greeting = (() => {
    const h = now.getHours();
    if (h < 12) return "Good morning";
    if (h < 17) return "Good afternoon";
    return "Good evening";
  })();

  return (
    <PageShell
      title="Home"
      subtitle={`${greeting}. Here's your day at a glance.`}
      headerActions={
        <Link href="/" className="btn btn-primary">Open Chat →</Link>
      }
    >
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
        {/* Left column */}
        <div>
          {/* Tasks due this week */}
          <Section
            title="Tasks Due This Week"
            count={tasks.length}
            viewAllHref="/tasks"
            empty={tasks.length === 0}
          >
            {loadingTasks ? (
              <div className="loading-skeleton">
                {[1, 2, 3].map((i) => <div key={i} className="loading-skeleton-row" style={{ height: "2.25rem" }} />)}
              </div>
            ) : tasks.length === 0 ? (
              <p style={{ color: "var(--text-muted)", fontSize: "0.875rem", margin: 0 }}>
                No tasks due this week. <Link href="/tasks" style={{ color: "var(--accent)" }}>View all tasks →</Link>
              </p>
            ) : (
              <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: "0.375rem" }}>
                {tasks.map((t) => {
                  const due = dueDateLabel(t.due_date);
                  return (
                    <li key={t.task_id} style={{ display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.375rem 0", borderBottom: "1px solid var(--border)" }}>
                      <span
                        style={{
                          display: "inline-block",
                          width: "8px",
                          height: "8px",
                          borderRadius: "50%",
                          background:
                            t.priority === "urgent" ? "var(--danger)" :
                            t.priority === "high"   ? "#d97706" :
                            "var(--text-muted)",
                          flexShrink: 0,
                        }}
                      />
                      <span style={{ flex: 1, fontSize: "0.875rem", color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {t.title}
                      </span>
                      {due && <span style={{ fontSize: "0.75rem", color: due.color, flexShrink: 0 }}>{due.label}</span>}
                    </li>
                  );
                })}
              </ul>
            )}
          </Section>

          {/* Pending approvals */}
          <Section
            title="Pending Approvals"
            count={approvals.length}
            viewAllHref="/approvals"
            empty={approvals.length === 0}
          >
            {loadingApprovals ? (
              <div className="loading-skeleton">
                <div className="loading-skeleton-row" style={{ height: "3rem" }} />
              </div>
            ) : approvals.length === 0 ? (
              <p style={{ color: "var(--text-muted)", fontSize: "0.875rem", margin: 0 }}>No pending approvals.</p>
            ) : (
              <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                {approvals.slice(0, 5).map((a) => (
                  <li key={a.request_id} style={{ padding: "0.625rem 0.75rem", background: "var(--surface)", borderRadius: "var(--radius-s)", border: "1px solid var(--border)" }}>
                    <p style={{ margin: "0 0 0.25rem", fontSize: "0.875rem", color: "var(--text)", fontWeight: 500 }}>
                      {a.summary || a.action_type}
                    </p>
                    <p style={{ margin: "0 0 0.5rem", fontSize: "0.75rem", color: "var(--text-muted)" }}>
                      {relTime(a.created_at)}
                    </p>
                    <div style={{ display: "flex", gap: "0.375rem" }}>
                      <button
                        className="btn btn-sm"
                        style={{ background: "var(--success)", color: "white", border: "none", padding: "0.25rem 0.625rem", borderRadius: "var(--radius-s)", cursor: "pointer", fontSize: "0.8125rem" }}
                        onClick={() => handleApprove(a.request_id)}
                      >
                        Approve
                      </button>
                      <button
                        className="btn btn-sm btn-secondary"
                        style={{ padding: "0.25rem 0.625rem", borderRadius: "var(--radius-s)", fontSize: "0.8125rem" }}
                        onClick={() => handleReject(a.request_id)}
                      >
                        Reject
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Section>
        </div>

        {/* Right column */}
        <div>
          {/* Active alerts */}
          <Section
            title="Alerts"
            count={alerts.length}
            empty={alerts.length === 0}
          >
            {loadingAlerts ? (
              <div className="loading-skeleton">
                <div className="loading-skeleton-row" style={{ height: "3rem" }} />
              </div>
            ) : alerts.length === 0 ? (
              <p style={{ color: "var(--text-muted)", fontSize: "0.875rem", margin: 0 }}>No active alerts.</p>
            ) : (
              <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                {alerts.map((a, i) => (
                  <li key={a.alert_id ?? a.id ?? i} style={{ display: "flex", gap: "0.625rem", padding: "0.5rem 0", borderBottom: "1px solid var(--border)" }}>
                    <span style={{ color: SEVERITY_COLORS[a.severity] ?? "var(--text-muted)", fontWeight: 700, fontSize: "0.75rem", flexShrink: 0, marginTop: "0.125rem" }}>
                      {a.severity === "critical" ? "●" : a.severity === "warning" ? "◆" : "●"}
                    </span>
                    <div>
                      <p style={{ margin: 0, fontSize: "0.875rem", fontWeight: 500, color: "var(--text)" }}>{a.title}</p>
                      <p style={{ margin: "0.125rem 0 0", fontSize: "0.8125rem", color: "var(--text-muted)" }}>{a.body}</p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Section>

          {/* Recent decisions */}
          <Section
            title="Recent Decisions"
            count={decisions.length}
            viewAllHref="/"
            empty={decisions.length === 0}
          >
            {loadingDecisions ? (
              <div className="loading-skeleton">
                {[1, 2].map((i) => <div key={i} className="loading-skeleton-row" style={{ height: "2.5rem" }} />)}
              </div>
            ) : decisions.length === 0 ? (
              <p style={{ color: "var(--text-muted)", fontSize: "0.875rem", margin: 0 }}>
                No decisions logged yet.{" "}
                <Link href="/" style={{ color: "var(--accent)" }}>Ask Friday to log one →</Link>
              </p>
            ) : (
              <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                {decisions.map((d) => (
                  <li key={d.decision_id} style={{ padding: "0.375rem 0", borderBottom: "1px solid var(--border)" }}>
                    <p style={{ margin: 0, fontSize: "0.875rem", fontWeight: 500, color: "var(--text)" }}>{d.title}</p>
                    <p style={{ margin: "0.125rem 0 0", fontSize: "0.75rem", color: "var(--text-muted)" }}>
                      {d.decision_maker} · {relTime(d.decided_at)}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Section>
        </div>
      </div>

      {/* Activity feed */}
      <div className="card" style={{ marginTop: "0.5rem" }}>
        <div className="card-header">
          <span style={{ fontWeight: 600, fontSize: "0.9375rem" }}>Recent Activity</span>
          {activity.length > 0 && (
            <span style={{ fontSize: "0.6875rem", fontWeight: 600, padding: "0.125rem 0.4rem", borderRadius: "999px", background: "var(--surface)", color: "var(--text-muted)", border: "1px solid var(--border)" }}>
              {activity.length}
            </span>
          )}
        </div>
        <div className="card-body">
          {loadingActivity ? (
            <div className="loading-skeleton">
              {[1, 2, 3].map((i) => <div key={i} className="loading-skeleton-row" style={{ height: "2rem" }} />)}
            </div>
          ) : activity.length === 0 ? (
            <p style={{ color: "var(--text-muted)", fontSize: "0.875rem", margin: 0 }}>No activity yet. Create a task or log an OKR check-in to get started.</p>
          ) : (
            <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: "0" }}>
              {activity.map((a) => {
                const icon =
                  a.action.startsWith("task") ? "✅" :
                  a.action.startsWith("okr") ? "🎯" :
                  a.action.startsWith("kr") ? "📊" :
                  a.action.startsWith("objective") ? "🎯" :
                  a.action.startsWith("decision") ? "⚖️" :
                  a.action.startsWith("process") ? "🔄" :
                  "📌";
                const label = a.action.replace(".", " ").replace(/_/g, " ");
                return (
                  <li key={a.activity_id} style={{ display: "flex", alignItems: "flex-start", gap: "0.625rem", padding: "0.5rem 0", borderBottom: "1px solid var(--border)" }}>
                    <span style={{ flexShrink: 0, fontSize: "0.875rem", marginTop: "1px" }}>{icon}</span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <span style={{ fontSize: "0.875rem", color: "var(--text)", fontWeight: 500 }}>
                        {a.entity_title || a.entity_id}
                      </span>
                      {" "}
                      <span style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>— {label}</span>
                    </div>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", flexShrink: 0, whiteSpace: "nowrap" }}>
                      {relTime(a.created_at)}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>

      {/* Ask Friday panel */}
      <div className="card" style={{ marginTop: "0.5rem", padding: "1rem 1.25rem" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <p style={{ margin: 0, fontWeight: 600, fontSize: "0.9375rem" }}>Ask Friday anything</p>
            <p style={{ margin: "0.25rem 0 0", fontSize: "0.8125rem", color: "var(--text-muted)" }}>
              Summarize my week · Create a task · Update OKR progress · Map a process
            </p>
          </div>
          <Link href="/" className="btn btn-primary">Open Chat →</Link>
        </div>
      </div>
    </PageShell>
  );
}
