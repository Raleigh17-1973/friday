"use client";

import React, { useEffect, useState, useCallback } from "react";
import { PageShell } from "@/components/page-shell";

const BACKEND = process.env.NEXT_PUBLIC_FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000";

// ── Types ──────────────────────────────────────────────────────────────────

interface OrgNode {
  node_id: string;
  name: string;
  node_type: string;
  parent_id: string | null;
  owner_user_id: string;
  org_id: string;
}

interface OKRPeriod {
  period_id: string;
  name: string;
  period_type: string;
  fiscal_year: number;
  quarter: number | null;
  start_date: string;
  end_date: string;
  status: string;
}

type Tab = "teams" | "periods";

// ── Helpers ────────────────────────────────────────────────────────────────

const NODE_TYPES = ["company", "division", "department", "team", "squad"] as const;
const PERIOD_TYPES = ["annual", "quarterly", "monthly", "custom"] as const;
const PERIOD_STATUSES: Record<string, { bg: string; color: string }> = {
  draft:  { bg: "#f3f4f6", color: "#6b7280" },
  active: { bg: "#f0fdf4", color: "#16a34a" },
  closed: { bg: "#fef2f2", color: "#dc2626" },
};

function Badge({ text, bg, color }: { text: string; bg: string; color: string }) {
  return (
    <span style={{ fontSize: "0.7rem", background: bg, color, borderRadius: "var(--radius-s)", padding: "2px 8px", textTransform: "capitalize", fontWeight: 500 }}>
      {text}
    </span>
  );
}

// ── Org Node Modal ─────────────────────────────────────────────────────────

interface NodeModalProps {
  nodes: OrgNode[];
  initial?: OrgNode | null;
  onClose: () => void;
  onSaved: () => void;
}

function NodeModal({ nodes, initial, onClose, onSaved }: NodeModalProps) {
  const [name, setName] = useState(initial?.name ?? "");
  const [nodeType, setNodeType] = useState<string>(initial?.node_type ?? "team");
  const [parentId, setParentId] = useState<string>(initial?.parent_id ?? "");
  const [owner, setOwner] = useState(initial?.owner_user_id ?? "user-1");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return setError("Name is required");
    setSaving(true);
    setError(null);
    const body = {
      name: name.trim(),
      node_type: nodeType,
      parent_id: parentId || null,
      owner_user_id: owner || "user-1",
      org_id: "org-1",
    };
    try {
      const url = initial
        ? `${BACKEND}/okrs/org-nodes/${initial.node_id}`
        : `${BACKEND}/okrs/org-nodes`;
      const res = await fetch(url, {
        method: initial ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(await res.text());
      onSaved();
    } catch (err) {
      setError(String(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", zIndex: 200, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div className="card" style={{ width: 440, padding: "var(--space-4)" }}>
        <h2 style={{ margin: "0 0 var(--space-3)", fontSize: "1rem", fontWeight: 600 }}>
          {initial ? "Edit Team" : "Add Team / Org Node"}
        </h2>
        <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
          <label style={{ fontSize: "0.8rem", fontWeight: 500 }}>
            Name <span style={{ color: "#dc2626" }}>*</span>
            <input
              className="form-input"
              style={{ display: "block", width: "100%", marginTop: 4 }}
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g. Engineering, Product, Sales"
              autoFocus
            />
          </label>

          <label style={{ fontSize: "0.8rem", fontWeight: 500 }}>
            Node Type
            <select
              className="form-input"
              style={{ display: "block", width: "100%", marginTop: 4 }}
              value={nodeType}
              onChange={e => setNodeType(e.target.value)}
            >
              {NODE_TYPES.map(t => <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>)}
            </select>
          </label>

          <label style={{ fontSize: "0.8rem", fontWeight: 500 }}>
            Parent Node <span style={{ color: "var(--text-muted, #888)", fontWeight: 400 }}>(optional — blank = root)</span>
            <select
              className="form-input"
              style={{ display: "block", width: "100%", marginTop: 4 }}
              value={parentId}
              onChange={e => setParentId(e.target.value)}
            >
              <option value="">— None (root) —</option>
              {nodes
                .filter(n => !initial || n.node_id !== initial.node_id)
                .map(n => (
                  <option key={n.node_id} value={n.node_id}>{n.name} ({n.node_type})</option>
                ))
              }
            </select>
          </label>

          <label style={{ fontSize: "0.8rem", fontWeight: 500 }}>
            Owner User ID
            <input
              className="form-input"
              style={{ display: "block", width: "100%", marginTop: 4 }}
              value={owner}
              onChange={e => setOwner(e.target.value)}
              placeholder="user-1"
            />
          </label>

          {error && <p style={{ color: "#dc2626", fontSize: "0.8rem", margin: 0 }}>{error}</p>}

          <div style={{ display: "flex", gap: "var(--space-2)", justifyContent: "flex-end", marginTop: "var(--space-2)" }}>
            <button type="button" className="btn" onClick={onClose} disabled={saving}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? "Saving…" : initial ? "Save Changes" : "Create Team"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Period Modal ───────────────────────────────────────────────────────────

interface PeriodModalProps {
  initial?: OKRPeriod | null;
  onClose: () => void;
  onSaved: () => void;
}

function PeriodModal({ initial, onClose, onSaved }: PeriodModalProps) {
  const currentYear = new Date().getFullYear();
  const [name, setName] = useState(initial?.name ?? "");
  const [periodType, setPeriodType] = useState<string>(initial?.period_type ?? "quarterly");
  const [fiscalYear, setFiscalYear] = useState<number>(initial?.fiscal_year ?? currentYear);
  const [quarter, setQuarter] = useState<string>(initial?.quarter ? String(initial.quarter) : "");
  const [startDate, setStartDate] = useState(initial?.start_date ?? "");
  const [endDate, setEndDate] = useState(initial?.end_date ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Auto-generate name when type/year/quarter change and name is empty or auto-generated
  useEffect(() => {
    if (initial) return; // don't auto-name on edit
    if (periodType === "quarterly" && quarter) {
      setName(`Q${quarter} FY${fiscalYear}`);
    } else if (periodType === "annual") {
      setName(`FY${fiscalYear}`);
    } else if (periodType === "monthly" && startDate) {
      const d = new Date(startDate);
      setName(`${d.toLocaleString("default", { month: "long" })} ${fiscalYear}`);
    }
  }, [periodType, fiscalYear, quarter, startDate, initial]);

  // Auto-fill dates for quarterly periods
  useEffect(() => {
    if (initial || periodType !== "quarterly" || !quarter) return;
    const fy = fiscalYear;
    const q = parseInt(quarter);
    const qStart = [
      `${fy}-01-01`, `${fy}-04-01`, `${fy}-07-01`, `${fy}-10-01`
    ][q - 1];
    const qEnd = [
      `${fy}-03-31`, `${fy}-06-30`, `${fy}-09-30`, `${fy}-12-31`
    ][q - 1];
    if (qStart) setStartDate(qStart);
    if (qEnd) setEndDate(qEnd);
  }, [quarter, fiscalYear, periodType, initial]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return setError("Name is required");
    setSaving(true);
    setError(null);
    const body = {
      name: name.trim(),
      period_type: periodType,
      fiscal_year: fiscalYear,
      quarter: quarter ? parseInt(quarter) : null,
      start_date: startDate || null,
      end_date: endDate || null,
      org_id: "org-1",
    };
    try {
      const url = initial
        ? `${BACKEND}/okrs/periods/${initial.period_id}`
        : `${BACKEND}/okrs/periods`;
      const res = await fetch(url, {
        method: initial ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(await res.text());
      onSaved();
    } catch (err) {
      setError(String(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", zIndex: 200, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div className="card" style={{ width: 460, padding: "var(--space-4)", maxHeight: "90vh", overflowY: "auto" }}>
        <h2 style={{ margin: "0 0 var(--space-3)", fontSize: "1rem", fontWeight: 600 }}>
          {initial ? "Edit Period" : "Add OKR Period"}
        </h2>
        <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>

          <label style={{ fontSize: "0.8rem", fontWeight: 500 }}>
            Period Type
            <select
              className="form-input"
              style={{ display: "block", width: "100%", marginTop: 4 }}
              value={periodType}
              onChange={e => setPeriodType(e.target.value)}
            >
              {PERIOD_TYPES.map(t => <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>)}
            </select>
          </label>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-2)" }}>
            <label style={{ fontSize: "0.8rem", fontWeight: 500 }}>
              Fiscal Year
              <input
                type="number"
                className="form-input"
                style={{ display: "block", width: "100%", marginTop: 4 }}
                value={fiscalYear}
                min={2020}
                max={2040}
                onChange={e => setFiscalYear(parseInt(e.target.value) || currentYear)}
              />
            </label>

            {periodType === "quarterly" && (
              <label style={{ fontSize: "0.8rem", fontWeight: 500 }}>
                Quarter
                <select
                  className="form-input"
                  style={{ display: "block", width: "100%", marginTop: 4 }}
                  value={quarter}
                  onChange={e => setQuarter(e.target.value)}
                >
                  <option value="">Select quarter</option>
                  {[1, 2, 3, 4].map(q => <option key={q} value={q}>Q{q}</option>)}
                </select>
              </label>
            )}
          </div>

          <label style={{ fontSize: "0.8rem", fontWeight: 500 }}>
            Display Name <span style={{ color: "#dc2626" }}>*</span>
            <input
              className="form-input"
              style={{ display: "block", width: "100%", marginTop: 4 }}
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g. Q2 FY2026"
            />
          </label>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-2)" }}>
            <label style={{ fontSize: "0.8rem", fontWeight: 500 }}>
              Start Date
              <input
                type="date"
                className="form-input"
                style={{ display: "block", width: "100%", marginTop: 4 }}
                value={startDate}
                onChange={e => setStartDate(e.target.value)}
              />
            </label>
            <label style={{ fontSize: "0.8rem", fontWeight: 500 }}>
              End Date
              <input
                type="date"
                className="form-input"
                style={{ display: "block", width: "100%", marginTop: 4 }}
                value={endDate}
                onChange={e => setEndDate(e.target.value)}
              />
            </label>
          </div>

          {error && <p style={{ color: "#dc2626", fontSize: "0.8rem", margin: 0 }}>{error}</p>}

          <div style={{ display: "flex", gap: "var(--space-2)", justifyContent: "flex-end", marginTop: "var(--space-2)" }}>
            <button type="button" className="btn" onClick={onClose} disabled={saving}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? "Saving…" : initial ? "Save Changes" : "Create Period"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────

export default function OKRSetupPage() {
  const [tab, setTab] = useState<Tab>("teams");

  // Org Nodes
  const [nodes, setNodes] = useState<OrgNode[]>([]);
  const [nodesLoading, setNodesLoading] = useState(true);
  const [nodeModal, setNodeModal] = useState<{ open: boolean; editing: OrgNode | null }>({ open: false, editing: null });

  // Periods
  const [periods, setPeriods] = useState<OKRPeriod[]>([]);
  const [periodsLoading, setPeriodsLoading] = useState(true);
  const [periodModal, setPeriodModal] = useState<{ open: boolean; editing: OKRPeriod | null }>({ open: false, editing: null });

  const [actionError, setActionError] = useState<string | null>(null);

  // ── Loaders ──────────────────────────────────────────────────────────────

  const loadNodes = useCallback(() => {
    setNodesLoading(true);
    fetch(`${BACKEND}/okrs/org-nodes?org_id=org-1`)
      .then(r => r.json())
      .then(d => { setNodes(d.org_nodes ?? d.nodes ?? []); setNodesLoading(false); })
      .catch(() => setNodesLoading(false));
  }, []);

  const loadPeriods = useCallback(() => {
    setPeriodsLoading(true);
    fetch(`${BACKEND}/okrs/periods?org_id=org-1`)
      .then(r => r.json())
      .then(d => { setPeriods(d.periods ?? d ?? []); setPeriodsLoading(false); })
      .catch(() => setPeriodsLoading(false));
  }, []);

  useEffect(() => { loadNodes(); loadPeriods(); }, [loadNodes, loadPeriods]);

  // ── Period status actions ──────────────────────────────────────────────────

  async function setPeriodStatus(periodId: string, status: string) {
    setActionError(null);
    try {
      const res = await fetch(`${BACKEND}/okrs/periods/${periodId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      if (!res.ok) throw new Error(await res.text());
      loadPeriods();
    } catch (err) {
      setActionError(String(err));
    }
  }

  // ── Helpers ──────────────────────────────────────────────────────────────

  function nodeParentName(node: OrgNode): string {
    if (!node.parent_id) return "—";
    return nodes.find(n => n.node_id === node.parent_id)?.name ?? node.parent_id;
  }

  const tabStyle = (t: Tab): React.CSSProperties => ({
    padding: "var(--space-2) var(--space-3)",
    background: tab === t ? "var(--accent)" : "transparent",
    color: tab === t ? "#fff" : "var(--text-muted, #888)",
    border: "none",
    borderRadius: "var(--radius-s) var(--radius-s) 0 0",
    cursor: "pointer",
    fontWeight: 500,
    fontSize: "0.875rem",
  });

  return (
    <PageShell
      title="OKR Setup"
      subtitle="Configure org teams and planning periods before creating objectives"
      breadcrumbs={[{ label: "OKRs", href: "/okrs" }, { label: "Setup" }]}
      headerActions={
        <a href="/okrs" className="btn" style={{ fontSize: "0.875rem" }}>← Back to OKRs</a>
      }
    >
      {/* Info banner */}
      <div style={{ background: "#eff6ff", border: "1px solid #bfdbfe", borderRadius: "var(--radius-s)", padding: "var(--space-2) var(--space-3)", marginBottom: "var(--space-3)", fontSize: "0.875rem", color: "#1e40af" }}>
        <strong>Setup required before creating objectives.</strong> Org teams define who owns objectives. Periods scope your OKR cycles (e.g. Q2 FY2026). Create these first, then go to{" "}
        <a href="/okrs/plan" style={{ color: "#1d4ed8" }}>OKR Plan</a> to draft objectives.
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", borderBottom: "2px solid var(--border)", marginBottom: "var(--space-3)" }}>
        <button style={tabStyle("teams")} onClick={() => setTab("teams")}>
          🏢 Teams &amp; Org Nodes {nodes.length > 0 && <span style={{ marginLeft: 6, background: "rgba(255,255,255,0.25)", borderRadius: 10, padding: "1px 7px", fontSize: "0.75rem" }}>{nodes.length}</span>}
        </button>
        <button style={tabStyle("periods")} onClick={() => setTab("periods")}>
          📅 OKR Periods {periods.length > 0 && <span style={{ marginLeft: 6, background: "rgba(255,255,255,0.25)", borderRadius: 10, padding: "1px 7px", fontSize: "0.75rem" }}>{periods.length}</span>}
        </button>
      </div>

      {actionError && (
        <div style={{ marginBottom: "var(--space-2)", color: "#dc2626", fontSize: "0.8rem" }}>Error: {actionError}</div>
      )}

      {/* ── Teams Tab ────────────────────────────────────────────────────── */}
      {tab === "teams" && (
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-2)" }}>
            <p style={{ margin: 0, fontSize: "0.875rem", color: "var(--text-muted, #888)" }}>
              Org nodes represent organizational units (companies, divisions, departments, teams, squads). Objectives are scoped to a team.
            </p>
            <button
              className="btn btn-primary"
              onClick={() => setNodeModal({ open: true, editing: null })}
            >
              + Add Team
            </button>
          </div>

          {nodesLoading ? (
            <p style={{ color: "var(--text-muted, #888)" }}>Loading teams…</p>
          ) : nodes.length === 0 ? (
            <div className="card" style={{ padding: "var(--space-4)", textAlign: "center", color: "var(--text-muted, #888)" }}>
              <div style={{ fontSize: "2rem", marginBottom: "var(--space-2)" }}>🏢</div>
              <p style={{ margin: "0 0 var(--space-2)" }}>No teams configured yet.</p>
              <button className="btn btn-primary" onClick={() => setNodeModal({ open: true, editing: null })}>
                Create your first team
              </button>
            </div>
          ) : (
            <div className="card" style={{ overflow: "hidden" }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ background: "var(--bg)", borderBottom: "2px solid var(--border)" }}>
                    {["Name", "Type", "Parent", "Owner", "Actions"].map(h => (
                      <th key={h} style={{ textAlign: "left", padding: "var(--space-2) var(--space-3)", fontSize: "0.75rem", fontWeight: 600, color: "var(--text-muted, #888)", textTransform: "uppercase", letterSpacing: "0.05em" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {nodes.map((node, i) => (
                    <tr key={node.node_id} style={{ borderBottom: i < nodes.length - 1 ? "1px solid var(--border)" : "none" }}>
                      <td style={{ padding: "var(--space-2) var(--space-3)", fontWeight: 500 }}>{node.name}</td>
                      <td style={{ padding: "var(--space-2) var(--space-3)" }}>
                        <Badge text={node.node_type} bg="#f3f4f6" color="#374151" />
                      </td>
                      <td style={{ padding: "var(--space-2) var(--space-3)", fontSize: "0.875rem", color: "var(--text-muted, #888)" }}>
                        {nodeParentName(node)}
                      </td>
                      <td style={{ padding: "var(--space-2) var(--space-3)", fontSize: "0.875rem", color: "var(--text-muted, #888)" }}>
                        {node.owner_user_id}
                      </td>
                      <td style={{ padding: "var(--space-2) var(--space-3)" }}>
                        <button
                          className="btn"
                          style={{ fontSize: "0.75rem", padding: "2px 10px" }}
                          onClick={() => setNodeModal({ open: true, editing: node })}
                        >
                          Edit
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── Periods Tab ─────────────────────────────────────────────────── */}
      {tab === "periods" && (
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-2)" }}>
            <p style={{ margin: 0, fontSize: "0.875rem", color: "var(--text-muted, #888)" }}>
              Periods define your OKR planning cycles. Create a period, then activate it to start creating objectives.
            </p>
            <button
              className="btn btn-primary"
              onClick={() => setPeriodModal({ open: true, editing: null })}
            >
              + Add Period
            </button>
          </div>

          {periodsLoading ? (
            <p style={{ color: "var(--text-muted, #888)" }}>Loading periods…</p>
          ) : periods.length === 0 ? (
            <div className="card" style={{ padding: "var(--space-4)", textAlign: "center", color: "var(--text-muted, #888)" }}>
              <div style={{ fontSize: "2rem", marginBottom: "var(--space-2)" }}>📅</div>
              <p style={{ margin: "0 0 var(--space-2)" }}>No OKR periods configured yet.</p>
              <button className="btn btn-primary" onClick={() => setPeriodModal({ open: true, editing: null })}>
                Create your first period
              </button>
            </div>
          ) : (
            <div className="card" style={{ overflow: "hidden" }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ background: "var(--bg)", borderBottom: "2px solid var(--border)" }}>
                    {["Name", "Type", "Year", "Quarter", "Start", "End", "Status", "Actions"].map(h => (
                      <th key={h} style={{ textAlign: "left", padding: "var(--space-2) var(--space-3)", fontSize: "0.75rem", fontWeight: 600, color: "var(--text-muted, #888)", textTransform: "uppercase", letterSpacing: "0.05em" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {periods.map((period, i) => {
                    const statusStyle = PERIOD_STATUSES[period.status] ?? { bg: "#f3f4f6", color: "#6b7280" };
                    return (
                      <tr key={period.period_id} style={{ borderBottom: i < periods.length - 1 ? "1px solid var(--border)" : "none" }}>
                        <td style={{ padding: "var(--space-2) var(--space-3)", fontWeight: 500 }}>{period.name}</td>
                        <td style={{ padding: "var(--space-2) var(--space-3)" }}>
                          <Badge text={period.period_type} bg="#eff6ff" color="#1d4ed8" />
                        </td>
                        <td style={{ padding: "var(--space-2) var(--space-3)", fontSize: "0.875rem" }}>{period.fiscal_year}</td>
                        <td style={{ padding: "var(--space-2) var(--space-3)", fontSize: "0.875rem", color: "var(--text-muted, #888)" }}>
                          {period.quarter ? `Q${period.quarter}` : "—"}
                        </td>
                        <td style={{ padding: "var(--space-2) var(--space-3)", fontSize: "0.8rem", color: "var(--text-muted, #888)" }}>
                          {period.start_date || "—"}
                        </td>
                        <td style={{ padding: "var(--space-2) var(--space-3)", fontSize: "0.8rem", color: "var(--text-muted, #888)" }}>
                          {period.end_date || "—"}
                        </td>
                        <td style={{ padding: "var(--space-2) var(--space-3)" }}>
                          <Badge text={period.status} bg={statusStyle.bg} color={statusStyle.color} />
                        </td>
                        <td style={{ padding: "var(--space-2) var(--space-3)" }}>
                          <div style={{ display: "flex", gap: "var(--space-1)" }}>
                            <button
                              className="btn"
                              style={{ fontSize: "0.75rem", padding: "2px 10px" }}
                              onClick={() => setPeriodModal({ open: true, editing: period })}
                            >
                              Edit
                            </button>
                            {period.status === "draft" && (
                              <button
                                className="btn"
                                style={{ fontSize: "0.75rem", padding: "2px 10px", color: "#16a34a", borderColor: "#16a34a" }}
                                onClick={() => setPeriodStatus(period.period_id, "active")}
                              >
                                Activate
                              </button>
                            )}
                            {period.status === "active" && (
                              <button
                                className="btn"
                                style={{ fontSize: "0.75rem", padding: "2px 10px", color: "#dc2626", borderColor: "#dc2626" }}
                                onClick={() => setPeriodStatus(period.period_id, "closed")}
                              >
                                Close
                              </button>
                            )}
                            {period.status === "closed" && (
                              <button
                                className="btn"
                                style={{ fontSize: "0.75rem", padding: "2px 10px", color: "#6b7280" }}
                                onClick={() => setPeriodStatus(period.period_id, "active")}
                              >
                                Reopen
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Modals */}
      {nodeModal.open && (
        <NodeModal
          nodes={nodes}
          initial={nodeModal.editing}
          onClose={() => setNodeModal({ open: false, editing: null })}
          onSaved={() => { setNodeModal({ open: false, editing: null }); loadNodes(); }}
        />
      )}

      {periodModal.open && (
        <PeriodModal
          initial={periodModal.editing}
          onClose={() => setPeriodModal({ open: false, editing: null })}
          onSaved={() => { setPeriodModal({ open: false, editing: null }); loadPeriods(); }}
        />
      )}
    </PageShell>
  );
}
