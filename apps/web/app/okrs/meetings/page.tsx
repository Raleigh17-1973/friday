"use client";

import { useEffect, useState } from "react";
import { PageShell } from "@/components/page-shell";

const BACKEND = process.env.NEXT_PUBLIC_FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000";

interface MeetingArtifact {
  artifact_id: string; meeting_type: string; generated_at: string;
  agenda_markdown: string; pre_read_markdown: string;
  decisions_markdown: string; org_node_id: string | null; period_id: string | null;
}
interface Period { period_id: string; name: string; }
interface OrgNode { node_id: string; name: string; }

const MEETING_LABELS: Record<string, string> = {
  weekly_checkin: "Weekly Check-in",
  portfolio_review: "Portfolio Review",
  quarterly_review: "Quarterly Review",
  planning_workshop: "Planning Workshop",
};
const MEETING_COLORS: Record<string, string> = {
  weekly_checkin: "#0891b2",
  portfolio_review: "#9333ea",
  quarterly_review: "var(--accent)",
  planning_workshop: "#16a34a",
};

export default function MeetingsPage() {
  const [artifacts, setArtifacts] = useState<MeetingArtifact[]>([]);
  const [periods, setPeriods] = useState<Period[]>([]);
  const [nodes, setNodes] = useState<OrgNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [showGenerate, setShowGenerate] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [generateForm, setGenerateForm] = useState({ meeting_type: "weekly_checkin", org_node_id: "", period_id: "" });
  const [selected, setSelected] = useState<MeetingArtifact | null>(null);

  async function load() {
    setLoading(true);
    try {
      const [artRes, periodRes, nodeRes] = await Promise.all([
        fetch(`${BACKEND}/okrs/meetings?org_id=org-1`),
        fetch(`${BACKEND}/okrs/periods?org_id=org-1`),
        fetch(`${BACKEND}/okrs/org-nodes?org_id=org-1`),
      ]);
      setArtifacts((await artRes.json()).artifacts ?? []);
      setPeriods((await periodRes.json()).periods ?? []);
      setNodes((await nodeRes.json()).org_nodes ?? []);
    } catch { /* ignore */ }
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  async function generate(e: React.FormEvent) {
    e.preventDefault();
    setGenerating(true);
    try {
      const res = await fetch(`${BACKEND}/okrs/meetings/generate`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...generateForm, org_id: "org-1" }),
      });
      if (res.ok) {
        const art = await res.json();
        setShowGenerate(false);
        setGenerateForm({ meeting_type: "weekly_checkin", org_node_id: "", period_id: "" });
        await load();
        setSelected(art);
      }
    } catch { /* ignore */ }
    setGenerating(false);
  }

  const nodeName = (id: string | null) => nodes.find(n => n.node_id === id)?.name ?? "All Teams";
  const periodName = (id: string | null) => periods.find(p => p.period_id === id)?.name ?? "—";

  return (
    <PageShell
      title="Meeting Packets"
      subtitle="Auto-generated preparation materials for OKR meetings"
      breadcrumbs={[{ label: "OKRs", href: "/okrs" }, { label: "Meeting Packets" }]}
      headerActions={<button className="btn btn-primary" onClick={() => setShowGenerate(true)}>+ Generate Packet</button>}
    >
      {loading ? <p>Loading…</p> : (
        <div style={{ display: "grid", gridTemplateColumns: selected ? "300px 1fr" : "1fr", gap: "var(--space-3)" }}>
          {/* List */}
          <div>
            {artifacts.length === 0 ? (
              <div className="card" style={{ padding: "var(--space-4)", textAlign: "center", color: "var(--text-muted, #888)" }}>
                <p style={{ marginBottom: "var(--space-2)" }}>No meeting packets yet</p>
                <button className="btn btn-primary" onClick={() => setShowGenerate(true)}>Generate Your First Packet</button>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
                {artifacts.map(a => (
                  <div key={a.artifact_id} className="card" style={{ padding: "var(--space-2)", cursor: "pointer", border: selected?.artifact_id === a.artifact_id ? "2px solid var(--accent)" : "2px solid transparent" }} onClick={() => setSelected(a)}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                      <span style={{ background: MEETING_COLORS[a.meeting_type] ?? "#888", color: "#fff", borderRadius: "var(--radius-s)", padding: "1px 6px", fontSize: "0.65rem", fontWeight: 600 }}>
                        {MEETING_LABELS[a.meeting_type] ?? a.meeting_type}
                      </span>
                      <span style={{ fontSize: "0.65rem", color: "var(--text-muted, #888)" }}>{new Date(a.generated_at).toLocaleDateString()}</span>
                    </div>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted, #888)", marginTop: 4 }}>
                      {nodeName(a.org_node_id)} · {periodName(a.period_id)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Detail panel */}
          {selected && (
            <div className="card" style={{ padding: "var(--space-3)", overflow: "auto" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
                <div>
                  <span style={{ background: MEETING_COLORS[selected.meeting_type] ?? "#888", color: "#fff", borderRadius: "var(--radius-s)", padding: "2px 8px", fontSize: "0.75rem", fontWeight: 600 }}>
                    {MEETING_LABELS[selected.meeting_type]}
                  </span>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-muted, #888)", marginLeft: 8 }}>{nodeName(selected.org_node_id)}</span>
                </div>
                <button className="btn" onClick={() => setSelected(null)} style={{ fontSize: "0.75rem" }}>✕ Close</button>
              </div>

              {selected.pre_read_markdown && (
                <div style={{ marginBottom: "var(--space-3)" }}>
                  <h4 style={{ fontSize: "0.875rem", marginBottom: "var(--space-1)" }}>Pre-Read</h4>
                  <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.8rem", color: "var(--text-muted, #888)", background: "var(--surface)", padding: "var(--space-2)", borderRadius: "var(--radius-s)" }}>{selected.pre_read_markdown}</pre>
                </div>
              )}
              {selected.agenda_markdown && (
                <div style={{ marginBottom: "var(--space-3)" }}>
                  <h4 style={{ fontSize: "0.875rem", marginBottom: "var(--space-1)" }}>Agenda</h4>
                  <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.8rem", background: "var(--surface)", padding: "var(--space-2)", borderRadius: "var(--radius-s)" }}>{selected.agenda_markdown}</pre>
                </div>
              )}
              {selected.decisions_markdown && (
                <div>
                  <h4 style={{ fontSize: "0.875rem", marginBottom: "var(--space-1)" }}>Decisions Needed</h4>
                  <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.8rem", color: "#eab308", background: "var(--surface)", padding: "var(--space-2)", borderRadius: "var(--radius-s)" }}>{selected.decisions_markdown}</pre>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Generate modal */}
      {showGenerate && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
          <div className="card" style={{ width: 440, padding: "var(--space-4)" }}>
            <h3 style={{ marginBottom: "var(--space-3)" }}>Generate Meeting Packet</h3>
            <form onSubmit={generate} style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
              <div>
                <label style={{ display: "block", marginBottom: 4, fontSize: "0.875rem" }}>Meeting Type *</label>
                <select className="form-input" style={{ width: "100%" }} value={generateForm.meeting_type} onChange={e => setGenerateForm(f => ({ ...f, meeting_type: e.target.value }))}>
                  <option value="weekly_checkin">Weekly Check-in</option>
                  <option value="portfolio_review">Portfolio Review</option>
                  <option value="quarterly_review">Quarterly Review</option>
                  <option value="planning_workshop">Planning Workshop</option>
                </select>
              </div>
              <div>
                <label style={{ display: "block", marginBottom: 4, fontSize: "0.875rem" }}>Team</label>
                <select className="form-input" style={{ width: "100%" }} value={generateForm.org_node_id} onChange={e => setGenerateForm(f => ({ ...f, org_node_id: e.target.value }))}>
                  <option value="">All teams</option>
                  {nodes.map(n => <option key={n.node_id} value={n.node_id}>{n.name}</option>)}
                </select>
              </div>
              <div>
                <label style={{ display: "block", marginBottom: 4, fontSize: "0.875rem" }}>Period</label>
                <select className="form-input" style={{ width: "100%" }} value={generateForm.period_id} onChange={e => setGenerateForm(f => ({ ...f, period_id: e.target.value }))}>
                  <option value="">No specific period</option>
                  {periods.map(p => <option key={p.period_id} value={p.period_id}>{p.name}</option>)}
                </select>
              </div>
              <div style={{ display: "flex", gap: "var(--space-2)", justifyContent: "flex-end", marginTop: "var(--space-1)" }}>
                <button type="button" className="btn" onClick={() => setShowGenerate(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={generating}>{generating ? "Generating…" : "Generate"}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </PageShell>
  );
}
