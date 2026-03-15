"use client";

import { useEffect, useState, useCallback } from "react";
import { PageShell } from "@/components/page-shell";

const BACKEND = process.env.NEXT_PUBLIC_FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000";

// ── Types ──────────────────────────────────────────────────────────────────────

type Approval = {
  approval_id: string;
  run_id: string;
  reason: string;
  action_summary: string;
  requested_scopes: string[];
  created_at: string;
  status: string;
};

type StatusFilter = "pending" | "all" | "approved" | "rejected";

// ── Helpers ────────────────────────────────────────────────────────────────────

function relTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const h = Math.floor(diff / 3600000);
  if (h < 1) return "just now";
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

const STATUS_STYLE: Record<string, { bg: string; color: string; label: string }> = {
  pending:  { bg: "#fef3c7", color: "#92400e", label: "Pending" },
  approved: { bg: "#dcfce7", color: "#166534", label: "Approved" },
  rejected: { bg: "#fee2e2", color: "#991b1b", label: "Rejected" },
};

// ── Row component ──────────────────────────────────────────────────────────────

function ApprovalRow({
  approval,
  selected,
  onToggle,
  onApprove,
  onReject,
}: {
  approval: Approval;
  selected: boolean;
  onToggle: () => void;
  onApprove: () => void;
  onReject: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const style = STATUS_STYLE[approval.status] ?? STATUS_STYLE.pending;

  return (
    <div
      style={{
        border: "1px solid var(--border)",
        borderRadius: "0.5rem",
        overflow: "hidden",
        background: selected ? "var(--surface)" : "var(--bg)",
        transition: "background 0.1s",
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: "0.75rem", padding: "0.875rem 1rem" }}>
        {/* Checkbox — only shown for pending */}
        {approval.status === "pending" && (
          <input
            type="checkbox"
            checked={selected}
            onChange={onToggle}
            style={{ marginTop: "3px", flexShrink: 0, cursor: "pointer" }}
          />
        )}
        <div style={{ flex: 1, minWidth: 0 }}>
          {/* Summary */}
          <div style={{ display: "flex", alignItems: "flex-start", gap: "0.625rem", marginBottom: "0.375rem" }}>
            <span
              style={{
                fontSize: "0.6875rem",
                fontWeight: 700,
                padding: "0.125rem 0.5rem",
                borderRadius: "9999px",
                background: style.bg,
                color: style.color,
                flexShrink: 0,
                marginTop: "2px",
              }}
            >
              {style.label}
            </span>
            <span style={{ fontSize: "0.9375rem", fontWeight: 500, color: "var(--text)", lineHeight: 1.4 }}>
              {approval.action_summary}
            </span>
          </div>

          {/* Scopes row */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.25rem", marginBottom: "0.375rem" }}>
            {approval.requested_scopes.map((s) => (
              <span
                key={s}
                style={{
                  fontSize: "0.6875rem",
                  fontFamily: "monospace",
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  borderRadius: "4px",
                  padding: "0.125rem 0.375rem",
                  color: "var(--accent)",
                }}
              >
                {s}
              </span>
            ))}
          </div>

          {/* Timestamp + expand */}
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
              {relTime(approval.created_at)}
            </span>
            <button
              className="btn btn-ghost btn-sm"
              style={{ fontSize: "0.72rem", padding: "0 6px" }}
              onClick={() => setExpanded((v) => !v)}
            >
              {expanded ? "Hide detail ↑" : "Show detail ↓"}
            </button>
          </div>
        </div>

        {/* Action buttons — only for pending */}
        {approval.status === "pending" && (
          <div style={{ display: "flex", gap: "0.375rem", flexShrink: 0 }}>
            <button
              className="btn btn-sm"
              style={{
                background: "#16a34a",
                color: "white",
                border: "none",
                padding: "0.3rem 0.75rem",
                borderRadius: "var(--radius-s)",
                cursor: "pointer",
                fontWeight: 600,
                fontSize: "0.8125rem",
              }}
              onClick={onApprove}
            >
              ✓ Approve
            </button>
            <button
              className="btn btn-sm btn-secondary"
              style={{ padding: "0.3rem 0.75rem", borderRadius: "var(--radius-s)", fontSize: "0.8125rem" }}
              onClick={onReject}
            >
              ✕ Reject
            </button>
          </div>
        )}
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div
          style={{
            borderTop: "1px solid var(--border)",
            padding: "0.75rem 1rem",
            background: "var(--surface)",
          }}
        >
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem", fontSize: "0.8125rem" }}>
            <div>
              <div style={{ fontWeight: 600, color: "var(--text-muted)", fontSize: "0.6875rem", textTransform: "uppercase", marginBottom: "0.25rem" }}>
                Policy Reason
              </div>
              <div style={{ color: "var(--text)", lineHeight: 1.5 }}>{approval.reason || "—"}</div>
            </div>
            <div>
              <div style={{ fontWeight: 600, color: "var(--text-muted)", fontSize: "0.6875rem", textTransform: "uppercase", marginBottom: "0.25rem" }}>
                Run ID
              </div>
              <div style={{ color: "var(--text)", fontFamily: "monospace", fontSize: "0.78rem" }}>{approval.run_id}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<StatusFilter>("pending");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkWorking, setBulkWorking] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const load = useCallback(() => {
    setLoading(true);
    setSelected(new Set());
    const statusParam = filter === "pending" ? "pending" : "all";
    fetch(`${BACKEND}/approvals?status=${statusParam}`)
      .then((r) => r.json())
      .then((data: unknown) => {
        const d = data as { approvals?: Approval[] };
        const all = d.approvals ?? [];
        if (filter === "approved") setApprovals(all.filter((a) => a.status === "approved"));
        else if (filter === "rejected") setApprovals(all.filter((a) => a.status === "rejected"));
        else setApprovals(all);
      })
      .catch(() => setApprovals([]))
      .finally(() => setLoading(false));
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  const handleSingle = async (id: string, decision: "approve" | "reject") => {
    const endpoint = `${BACKEND}/approvals/${id}/${decision}`;
    await fetch(endpoint, { method: "POST" }).catch(() => undefined);
    showToast(`${decision === "approve" ? "Approved" : "Rejected"} successfully`);
    load();
  };

  const handleBulk = async (decision: "approve" | "reject") => {
    if (selected.size === 0) return;
    setBulkWorking(true);
    try {
      await fetch(`${BACKEND}/approvals/bulk-decide`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approval_ids: [...selected], decision }),
      });
      showToast(`${decision === "approve" ? "Approved" : "Rejected"} ${selected.size} request${selected.size !== 1 ? "s" : ""}`);
      load();
    } finally {
      setBulkWorking(false);
    }
  };

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => {
    const pendingIds = approvals.filter((a) => a.status === "pending").map((a) => a.approval_id);
    setSelected(new Set(pendingIds));
  };

  const pendingCount = approvals.filter((a) => a.status === "pending").length;

  const FILTERS: { label: string; value: StatusFilter }[] = [
    { label: "Pending", value: "pending" },
    { label: "All", value: "all" },
    { label: "Approved", value: "approved" },
    { label: "Rejected", value: "rejected" },
  ];

  return (
    <PageShell
      title="Approvals"
      subtitle="Review and action write requests from Friday agents"
      headerActions={
        pendingCount > 0 ? (
          <span
            style={{
              fontSize: "0.75rem",
              fontWeight: 700,
              padding: "0.25rem 0.625rem",
              borderRadius: "9999px",
              background: "#fef3c7",
              color: "#92400e",
            }}
          >
            {pendingCount} pending
          </span>
        ) : undefined
      }
    >
      {/* Toast */}
      {toast && (
        <div
          style={{
            position: "fixed",
            bottom: "1.5rem",
            right: "1.5rem",
            background: "#1e293b",
            color: "white",
            padding: "0.625rem 1rem",
            borderRadius: "0.5rem",
            fontSize: "0.875rem",
            zIndex: 9999,
            boxShadow: "0 4px 12px rgba(0,0,0,0.25)",
          }}
        >
          {toast}
        </div>
      )}

      {/* Toolbar */}
      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem", flexWrap: "wrap" }}>
        {/* Filter pills */}
        <div style={{ display: "flex", gap: "0.25rem", background: "var(--surface)", borderRadius: "0.5rem", padding: "3px", border: "1px solid var(--border)" }}>
          {FILTERS.map((f) => (
            <button
              key={f.value}
              className={filter === f.value ? "btn btn-primary btn-sm" : "btn btn-ghost btn-sm"}
              style={{ borderRadius: "0.375rem", padding: "0.25rem 0.625rem", fontSize: "0.8125rem" }}
              onClick={() => setFilter(f.value)}
            >
              {f.label}
            </button>
          ))}
        </div>

        {/* Bulk actions — visible when ≥1 pending */}
        {filter === "pending" && pendingCount > 0 && (
          <>
            <button
              className="btn btn-ghost btn-sm"
              style={{ fontSize: "0.8125rem" }}
              onClick={selectAll}
            >
              Select all ({pendingCount})
            </button>
            {selected.size > 0 && (
              <>
                <button
                  className="btn btn-sm"
                  style={{ background: "#16a34a", color: "white", border: "none", padding: "0.3rem 0.75rem", borderRadius: "var(--radius-s)", cursor: "pointer", fontWeight: 600, fontSize: "0.8125rem" }}
                  disabled={bulkWorking}
                  onClick={() => handleBulk("approve")}
                >
                  {bulkWorking ? "…" : `✓ Approve ${selected.size}`}
                </button>
                <button
                  className="btn btn-sm btn-secondary"
                  style={{ padding: "0.3rem 0.75rem", borderRadius: "var(--radius-s)", fontSize: "0.8125rem" }}
                  disabled={bulkWorking}
                  onClick={() => handleBulk("reject")}
                >
                  {bulkWorking ? "…" : `✕ Reject ${selected.size}`}
                </button>
              </>
            )}
          </>
        )}
      </div>

      {/* List */}
      {loading ? (
        <div className="loading-skeleton">
          {[1, 2, 3].map((i) => <div key={i} className="loading-skeleton-row" style={{ height: "5rem", marginBottom: "0.5rem" }} />)}
        </div>
      ) : approvals.length === 0 ? (
        <div className="empty-state" style={{ padding: "3rem" }}>
          <div className="empty-state-icon">✅</div>
          <p className="empty-state-title">
            {filter === "pending" ? "No pending approvals" : "No approvals found"}
          </p>
          <p className="empty-state-body">
            {filter === "pending"
              ? "When Friday agents request write access, approval requests appear here."
              : "Switch the filter above to see approvals in other states."}
          </p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          {approvals.map((a) => (
            <ApprovalRow
              key={a.approval_id}
              approval={a}
              selected={selected.has(a.approval_id)}
              onToggle={() => toggleSelect(a.approval_id)}
              onApprove={() => handleSingle(a.approval_id, "approve")}
              onReject={() => handleSingle(a.approval_id, "reject")}
            />
          ))}
        </div>
      )}
    </PageShell>
  );
}
