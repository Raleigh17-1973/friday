"use client";

import { useEffect, useState, useCallback } from "react";
import { PageShell } from "@/components/page-shell";

const BACKEND = process.env.NEXT_PUBLIC_FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000";

interface OrgNode { node_id: string; name: string; node_type: string; parent_id: string | null; }
interface Period { period_id: string; name: string; period_type: string; fiscal_year: number; status: string; }
interface Objective {
  objective_id: string; title: string; objective_type: string;
  health_current: string; confidence_current: number; status: string;
  owner_user_id: string; org_node_id: string; period_id: string;
}
interface KPI { kpi_id: string; name: string; unit: string; current_value: number | null; health_status: string; target_band_low: number | null; target_band_high: number | null; }

const HEALTH_COLOR: Record<string, string> = { green: "#22c55e", yellow: "#eab308", red: "#ef4444" };
const TYPE_STYLE: Record<string, string> = { committed: "badge", aspirational: "badge" };

export default function OKRsPage() {
  const [objectives, setObjectives] = useState<Objective[]>([]);
  const [periods, setPeriods] = useState<Period[]>([]);
  const [nodes, setNodes] = useState<OrgNode[]>([]);
  const [kpis, setKpis] = useState<KPI[]>([]);
  const [selectedPeriod, setSelectedPeriod] = useState("");
  const [selectedNode, setSelectedNode] = useState("");
  const [selectedType, setSelectedType] = useState("");
  const [activeTab, setActiveTab] = useState("objectives");
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createForm, setCreateForm] = useState({
    title: "", objective_type: "committed", description: "", rationale: "",
    period_id: "", org_node_id: "", owner_user_id: "user-1", sponsor_user_id: "",
  });
  const [validationIssues, setValidationIssues] = useState<Array<{rule_id: string; severity: string; message: string}>>([]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [periodsRes, nodesRes] = await Promise.all([
        fetch(`${BACKEND}/okrs/periods?org_id=org-1`),
        fetch(`${BACKEND}/okrs/org-nodes?org_id=org-1`),
      ]);
      const periodsData = await periodsRes.json();
      const nodesData = await nodesRes.json();
      setPeriods(periodsData.periods ?? []);
      setNodes(nodesData.org_nodes ?? []);

      const params = new URLSearchParams({ org_id: "org-1" });
      if (selectedPeriod) params.set("period_id", selectedPeriod);
      if (selectedNode) params.set("org_node_id", selectedNode);
      if (selectedType) params.set("objective_type", selectedType);
      const objRes = await fetch(`${BACKEND}/okrs/objectives?${params}`);
      const objData = await objRes.json();
      setObjectives(objData.objectives ?? []);

      const kpiRes = await fetch(`${BACKEND}/okrs/kpis?org_id=org-1`);
      const kpiData = await kpiRes.json();
      setKpis(kpiData.kpis ?? []);
    } catch { /* ignore */ }
    setLoading(false);
  }, [selectedPeriod, selectedNode, selectedType]);

  useEffect(() => { loadData(); }, [loadData]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    try {
      const body = { ...createForm, org_id: "org-1" };
      const res = await fetch(`${BACKEND}/okrs/objectives`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      const data = await res.json();
      if (data.validation_issues) setValidationIssues(data.validation_issues);
      if (res.ok) {
        setShowCreate(false);
        setCreateForm({ title: "", objective_type: "committed", description: "", rationale: "", period_id: "", org_node_id: "", owner_user_id: "user-1", sponsor_user_id: "" });
        setValidationIssues([]);
        loadData();
      }
    } catch { /* ignore */ }
    setCreating(false);
  }

  // Stats
  const total = objectives.length;
  const committed = objectives.filter(o => o.objective_type === "committed").length;
  const atRisk = objectives.filter(o => o.health_current === "red").length;
  const avgConf = total > 0 ? Math.round((objectives.reduce((s, o) => s + (o.confidence_current ?? 0), 0) / total) * 100) : 0;

  const nodeName = (id: string) => nodes.find(n => n.node_id === id)?.name ?? id;
  const periodName = (id: string) => periods.find(p => p.period_id === id)?.name ?? id;

  // Detect unconfigured state: no periods AND no org nodes loaded (after loading finishes)
  const isUnconfigured = !loading && periods.length === 0 && nodes.length === 0;

  return (
    <PageShell
      title="OKRs"
      subtitle="Enterprise objectives and key results"
      headerActions={
        <div style={{ display: "flex", gap: "var(--space-1)" }}>
          <a href="/okrs/setup" className="btn" style={{ fontSize: "0.875rem" }}>⚙ Setup</a>
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}>+ New Objective</button>
        </div>
      }
    >
      {/* Setup required banner */}
      {isUnconfigured && (
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", background: "#fef3c7", border: "1px solid #fcd34d", borderRadius: "var(--radius-s)", padding: "var(--space-2) var(--space-3)", marginBottom: "var(--space-3)" }}>
          <span style={{ fontSize: "1.25rem" }}>⚠️</span>
          <div style={{ flex: 1 }}>
            <strong style={{ fontSize: "0.875rem", color: "#92400e" }}>Setup required before creating objectives</strong>
            <p style={{ margin: "2px 0 0", fontSize: "0.8rem", color: "#78350f" }}>
              No periods or teams are configured yet. Create at least one period and one team first.
            </p>
          </div>
          <a href="/okrs/setup" className="btn" style={{ fontSize: "0.8rem", background: "#92400e", color: "#fff", borderColor: "#92400e", whiteSpace: "nowrap" }}>
            Go to OKR Setup →
          </a>
        </div>
      )}

      {/* Filters */}
      <div style={{ display: "flex", gap: "var(--space-2)", marginBottom: "var(--space-3)", flexWrap: "wrap" }}>
        <select className="form-input" style={{ minWidth: 160 }} value={selectedPeriod} onChange={e => setSelectedPeriod(e.target.value)}>
          <option value="">All Periods</option>
          {periods.map(p => <option key={p.period_id} value={p.period_id}>{p.name}</option>)}
        </select>
        <select className="form-input" style={{ minWidth: 160 }} value={selectedNode} onChange={e => setSelectedNode(e.target.value)}>
          <option value="">All Teams</option>
          {nodes.map(n => <option key={n.node_id} value={n.node_id}>{n.name}</option>)}
        </select>
        <select className="form-input" style={{ minWidth: 160 }} value={selectedType} onChange={e => setSelectedType(e.target.value)}>
          <option value="">All Types</option>
          <option value="committed">Committed</option>
          <option value="aspirational">Aspirational</option>
        </select>
      </div>

      {/* Stats bar */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "var(--space-2)", marginBottom: "var(--space-3)" }}>
        {[
          { label: "Total Objectives", value: total },
          { label: "Committed", value: committed },
          { label: "At Risk", value: atRisk, danger: atRisk > 0 },
          { label: "Avg Confidence", value: `${avgConf}%` },
        ].map(s => (
          <div key={s.label} className="card" style={{ padding: "var(--space-2)", textAlign: "center" }}>
            <div style={{ fontSize: "1.5rem", fontWeight: 700, color: s.danger ? "var(--danger, #ef4444)" : "var(--accent)" }}>{s.value}</div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted, #888)", marginTop: 2 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: "var(--space-1)", marginBottom: "var(--space-3)", borderBottom: "1px solid var(--border)" }}>
        {["objectives", "kpis", "periods", "dashboards"].map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)}
            style={{ padding: "8px 16px", border: "none", background: "none", cursor: "pointer", fontWeight: activeTab === tab ? 600 : 400, borderBottom: activeTab === tab ? "2px solid var(--accent)" : "2px solid transparent", color: activeTab === tab ? "var(--accent)" : "var(--text-muted, #888)", textTransform: "capitalize" }}>
            {tab}
          </button>
        ))}
      </div>

      {/* Objectives tab */}
      {activeTab === "objectives" && (
        loading ? <p>Loading objectives…</p> : objectives.length === 0 ? (
          <div className="card" style={{ padding: "var(--space-4)", textAlign: "center", color: "var(--text-muted, #888)" }}>
            <p style={{ fontSize: "1.1rem", marginBottom: "var(--space-2)" }}>No objectives found</p>
            <p style={{ fontSize: "0.875rem" }}>Create your first objective to get started</p>
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: "var(--space-2)" }}>
            {objectives.map(obj => (
              <a key={obj.objective_id} href={`/okrs/${obj.objective_id}`} style={{ textDecoration: "none", color: "inherit" }}>
                <div className="card" style={{ padding: "var(--space-3)", height: "100%", transition: "box-shadow 0.15s", cursor: "pointer" }}>
                  <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "var(--space-1)", marginBottom: "var(--space-2)" }}>
                    <span style={{ fontSize: "0.875rem", fontWeight: 600, lineHeight: 1.4 }}>{obj.title}</span>
                    <span style={{ width: 10, height: 10, borderRadius: "50%", background: HEALTH_COLOR[obj.health_current] ?? "#888", flexShrink: 0, marginTop: 3 }} title={obj.health_current} />
                  </div>
                  <div style={{ display: "flex", gap: "var(--space-1)", flexWrap: "wrap", marginBottom: "var(--space-2)" }}>
                    <span className="badge" style={{ background: obj.objective_type === "committed" ? "var(--accent)" : "#7c3aed", color: "#fff", fontSize: "0.7rem" }}>
                      {obj.objective_type}
                    </span>
                    <span className="badge" style={{ fontSize: "0.7rem" }}>{obj.status}</span>
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted, #888)" }}>
                    <div>{nodeName(obj.org_node_id)}</div>
                    {obj.period_id && <div>{periodName(obj.period_id)}</div>}
                    <div style={{ marginTop: 4 }}>Confidence: {Math.round((obj.confidence_current ?? 0) * 100)}%</div>
                  </div>
                </div>
              </a>
            ))}
          </div>
        )
      )}

      {/* KPIs tab */}
      {activeTab === "kpis" && (
        <div>
          {kpis.length === 0 ? (
            <div className="card" style={{ padding: "var(--space-4)", textAlign: "center", color: "var(--text-muted, #888)" }}>No KPIs defined yet</div>
          ) : (
            <table className="data-table" style={{ width: "100%" }}>
              <thead><tr><th>Name</th><th>Unit</th><th>Current Value</th><th>Target Band</th><th>Health</th></tr></thead>
              <tbody>
                {kpis.map(k => (
                  <tr key={k.kpi_id}>
                    <td>{k.name}</td>
                    <td>{k.unit}</td>
                    <td>{k.current_value ?? "—"}</td>
                    <td>{k.target_band_low != null ? `${k.target_band_low} – ${k.target_band_high}` : "—"}</td>
                    <td><span style={{ color: HEALTH_COLOR[k.health_status] ?? "#888" }}>●</span> {k.health_status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Periods tab */}
      {activeTab === "periods" && (
        <div>
          <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: "var(--space-2)" }}>
            <a href="/okrs/setup" className="btn" style={{ fontSize: "0.8rem" }}>⚙ Manage Periods &amp; Teams →</a>
          </div>
          {periods.length === 0 ? (
            <div className="card" style={{ padding: "var(--space-4)", textAlign: "center", color: "var(--text-muted, #888)" }}>
              <p style={{ marginBottom: "var(--space-2)" }}>No periods configured yet.</p>
              <a href="/okrs/setup" className="btn btn-primary" style={{ fontSize: "0.875rem" }}>Create a Period →</a>
            </div>
          ) : (
            <table className="data-table" style={{ width: "100%" }}>
              <thead><tr><th>Name</th><th>Type</th><th>Fiscal Year</th><th>Quarter</th><th>Status</th></tr></thead>
              <tbody>
                {periods.map(p => (
                  <tr key={p.period_id}>
                    <td>{p.name}</td>
                    <td>{p.period_type}</td>
                    <td>{p.fiscal_year}</td>
                    <td>{(p as {quarter?: number}).quarter ?? "—"}</td>
                    <td><span className="badge">{p.status}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div style={{ marginTop: "var(--space-3)", display: "flex", gap: "var(--space-2)" }}>
            <a href="/okrs/dashboards/executive" className="btn">Executive Dashboard</a>
            <a href="/okrs/dashboards/team" className="btn">Team Dashboard</a>
            <a href="/okrs/meetings" className="btn">Meeting Packets</a>
          </div>
        </div>
      )}

      {/* Dashboards tab */}
      {activeTab === "dashboards" && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: "var(--space-2)" }}>
          {[
            { label: "Executive Dashboard", href: "/okrs/dashboards/executive", desc: "Company-wide OKR health, at-risk committed objectives, score vs confidence" },
            { label: "Team Dashboard", href: "/okrs/dashboards/team", desc: "Team-level objectives, pending check-ins, required actions" },
            { label: "Meeting Packets", href: "/okrs/meetings", desc: "Auto-generated prep for weekly check-ins, portfolio reviews, and planning workshops" },
            { label: "Planning Workspace", href: "/okrs/plan", desc: "Step-by-step wizard for creating and validating new OKRs" },
          ].map(d => (
            <a key={d.href} href={d.href} style={{ textDecoration: "none", color: "inherit" }}>
              <div className="card" style={{ padding: "var(--space-3)", height: "100%", cursor: "pointer" }}>
                <div style={{ fontWeight: 600, marginBottom: "var(--space-1)", color: "var(--accent)" }}>{d.label}</div>
                <div style={{ fontSize: "0.8rem", color: "var(--text-muted, #888)" }}>{d.desc}</div>
              </div>
            </a>
          ))}
        </div>
      )}

      {/* Create objective modal */}
      {showCreate && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
          <div className="card" style={{ width: 560, maxHeight: "90vh", overflow: "auto", padding: "var(--space-4)" }}>
            <h2 style={{ marginBottom: "var(--space-3)" }}>New Objective</h2>
            <form onSubmit={handleCreate} style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
              {isUnconfigured && (
                <div style={{ background: "#fef3c7", border: "1px solid #fcd34d", borderRadius: "var(--radius-s)", padding: "var(--space-2)", fontSize: "0.8rem", color: "#92400e" }}>
                  ⚠ No periods or teams configured. <a href="/okrs/setup" style={{ color: "#92400e", fontWeight: 600 }}>Set up OKRs first →</a>
                </div>
              )}
              <div>
                <label style={{ display: "block", marginBottom: 4, fontSize: "0.875rem", fontWeight: 500 }}>Period *</label>
                <select className="form-input" style={{ width: "100%" }} value={createForm.period_id} onChange={e => setCreateForm(f => ({ ...f, period_id: e.target.value }))} required>
                  <option value="">Select a period</option>
                  {periods.map(p => <option key={p.period_id} value={p.period_id}>{p.name}</option>)}
                </select>
                {periods.length === 0 && <p style={{ margin: "4px 0 0", fontSize: "0.75rem", color: "var(--text-muted,#888)" }}>No periods yet — <a href="/okrs/setup" style={{ color: "var(--accent)" }}>create one</a></p>}
              </div>
              <div>
                <label style={{ display: "block", marginBottom: 4, fontSize: "0.875rem", fontWeight: 500 }}>Team / Org Node *</label>
                <select className="form-input" style={{ width: "100%" }} value={createForm.org_node_id} onChange={e => setCreateForm(f => ({ ...f, org_node_id: e.target.value }))} required>
                  <option value="">Select a team</option>
                  {nodes.map(n => <option key={n.node_id} value={n.node_id}>{n.name}</option>)}
                </select>
                {nodes.length === 0 && <p style={{ margin: "4px 0 0", fontSize: "0.75rem", color: "var(--text-muted,#888)" }}>No teams yet — <a href="/okrs/setup" style={{ color: "var(--accent)" }}>create one</a></p>}
              </div>
              <div>
                <label style={{ display: "block", marginBottom: 4, fontSize: "0.875rem", fontWeight: 500 }}>Title *</label>
                <input className="form-input" style={{ width: "100%" }} type="text" placeholder="Become the undisputed market leader in SMB HR" value={createForm.title} onChange={e => setCreateForm(f => ({ ...f, title: e.target.value }))} required />
              </div>
              <div>
                <label style={{ display: "block", marginBottom: 4, fontSize: "0.875rem", fontWeight: 500 }}>Type</label>
                <select className="form-input" style={{ width: "100%" }} value={createForm.objective_type} onChange={e => setCreateForm(f => ({ ...f, objective_type: e.target.value }))}>
                  <option value="committed">Committed — team is expected to fully deliver</option>
                  <option value="aspirational">Aspirational — 0.7 score is not failure</option>
                </select>
              </div>
              <div>
                <label style={{ display: "block", marginBottom: 4, fontSize: "0.875rem", fontWeight: 500 }}>Rationale</label>
                <textarea className="form-input" style={{ width: "100%", minHeight: 60 }} placeholder="Why does this objective matter now?" value={createForm.rationale} onChange={e => setCreateForm(f => ({ ...f, rationale: e.target.value }))} />
              </div>
              {/* Validation issues */}
              {validationIssues.length > 0 && (
                <div style={{ padding: "var(--space-2)", background: "rgba(239,68,68,0.08)", borderRadius: "var(--radius-s)", border: "1px solid rgba(239,68,68,0.3)" }}>
                  {validationIssues.map(i => (
                    <div key={i.rule_id} style={{ fontSize: "0.8rem", color: i.severity === "error" ? "#ef4444" : "#eab308", marginBottom: 4 }}>
                      {i.severity === "error" ? "⚠" : "ℹ"} [{i.rule_id}] {i.message}
                    </div>
                  ))}
                </div>
              )}
              <div style={{ display: "flex", gap: "var(--space-2)", justifyContent: "flex-end", marginTop: "var(--space-1)" }}>
                <button type="button" className="btn" onClick={() => { setShowCreate(false); setValidationIssues([]); }}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={creating}>{creating ? "Creating…" : "Create Objective"}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </PageShell>
  );
}
