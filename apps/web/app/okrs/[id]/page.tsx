"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { PageShell } from "@/components/page-shell";

const BACKEND = process.env.NEXT_PUBLIC_FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000";

const HEALTH_COLOR: Record<string, string> = { green: "#22c55e", yellow: "#eab308", red: "#ef4444" };
const TYPE_BG: Record<string, string> = { committed: "var(--accent)", aspirational: "#7c3aed" };
const KR_TYPE_BG: Record<string, string> = { metric: "#0891b2", milestone: "#9333ea", binary: "#16a34a" };

interface Objective {
  objective_id: string; title: string; objective_type: string;
  health_current: string; confidence_current: number; status: string;
  description: string; rationale: string; owner_user_id: string;
  sponsor_user_id: string | null; period_id: string; org_node_id: string;
  score_final: number | null; quality_score: number | null;
  parent_objective_id: string | null; created_at: string;
  visibility: string; alignment_mode: string;
}
interface KeyResult {
  kr_id: string; title: string; kr_type: string; score_current: number;
  confidence_current: number; health_current: string; status: string;
  baseline_value: number | null; target_value: number | null;
  current_value: number | null; unit: string; direction: string;
  owner_user_id: string; due_date: string | null;
}
interface Checkin {
  checkin_id: string; object_type: string; object_id: string; checkin_date: string;
  current_value: number | null; confidence_snapshot: number | null;
  score_snapshot: number | null; blockers: string; decisions_needed: string;
  narrative_update: string; next_steps: string; user_id: string; created_at: string;
  parent_checkin_id: string | null;
}
interface CheckinChain {
  latest: Checkin;
  history: Checkin[];   // older versions, newest-first
}
interface Initiative {
  initiative_id: string; title: string; status: string;
  description: string; external_system_ref: string | null; owner_user_id: string;
}
interface Dependency {
  dependency_id: string; source_object_type: string; source_object_id: string;
  target_object_type: string; target_object_id: string;
  dependency_type: string; severity: string;
}

interface ObjectiveDetail extends Objective {
  key_results?: KeyResult[];
  checkins?: Checkin[];
  initiatives?: Initiative[];
  dependencies?: Dependency[];
}

interface PeerObjective {
  objective_id: string;
  title: string;
}

export default function OKRDetailPage() {
  const params = useParams();
  const id = params?.id as string;
  const [detail, setDetail] = useState<ObjectiveDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("key_results");

  // Check-in form — kr_id for new, or { kr_id, parent_checkin_id } for update
  const [showCheckinForm, setShowCheckinForm] = useState<string | null>(null);
  const [checkinParentId, setCheckinParentId] = useState<string | null>(null);
  const [checkinForm, setCheckinForm] = useState({ current_value: "", confidence: "0.7", blockers: "", decisions_needed: "", narrative_update: "", next_steps: "" });

  // History expansion per checkin chain (keyed by latest checkin_id)
  const [expandedHistory, setExpandedHistory] = useState<Set<string>>(new Set());

  // KR form
  const [showKrForm, setShowKrForm] = useState(false);
  const [krForm, setKrForm] = useState({ title: "", kr_type: "metric", baseline_value: "", target_value: "", unit: "", direction: "increase", description: "" });

  // Edit objective form
  const [showEditForm, setShowEditForm] = useState(false);
  const [editForm, setEditForm] = useState({
    title: "", description: "", rationale: "",
    objective_type: "committed", status: "active",
    owner_user_id: "", sponsor_user_id: "",
    visibility: "team", parent_objective_id: "",
  });
  const [peerObjectives, setPeerObjectives] = useState<PeerObjective[]>([]);
  const [editError, setEditError] = useState<string | null>(null);

  const [submitting, setSubmitting] = useState(false);

  async function loadDetail() {
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND}/okrs/objectives/${id}`);
      if (res.ok) {
        const data = await res.json();
        // API returns { objective: {...}, key_results: [...], checkins: [...], ... }
        // Unnest the objective fields and combine with related collections
        const objFields = data.objective ?? data;
        const krList: KeyResult[] = data.key_results ?? [];
        const objCheckins: Checkin[] = data.checkins ?? [];

        // Fetch KR-level check-ins in parallel for all key results
        const krCheckinLists = await Promise.all(
          krList.map((kr: KeyResult) =>
            fetch(`${BACKEND}/okrs/checkins?object_type=key_result&object_id=${kr.kr_id}`)
              .then(r => r.json())
              .then(d => (d.checkins ?? []) as Checkin[])
              .catch(() => [] as Checkin[])
          )
        );
        const allCheckins = [...objCheckins, ...krCheckinLists.flat()].sort(
          (a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? "")
        );

        setDetail({
          ...objFields,
          key_results: krList,
          checkins: allCheckins,
          initiatives: data.initiatives ?? [],
          dependencies: data.dependencies ?? [],
        });
      }
    } catch { /* ignore */ }
    setLoading(false);
  }

  useEffect(() => { if (id) loadDetail(); }, [id]);

  // Pre-fill edit form whenever detail loads
  useEffect(() => {
    if (!detail) return;
    setEditForm({
      title: detail.title ?? "",
      description: detail.description ?? "",
      rationale: detail.rationale ?? "",
      objective_type: detail.objective_type ?? "committed",
      status: detail.status ?? "active",
      owner_user_id: detail.owner_user_id ?? "",
      sponsor_user_id: detail.sponsor_user_id ?? "",
      visibility: detail.visibility ?? "team",
      parent_objective_id: detail.parent_objective_id ?? "",
    });
    // Load peer objectives for parent selector
    if (detail.period_id) {
      fetch(`${BACKEND}/okrs/objectives?period_id=${detail.period_id}&org_id=org-1`)
        .then(r => r.json())
        .then(d => {
          const peers: PeerObjective[] = (d.objectives ?? d ?? [])
            .filter((o: PeerObjective) => o.objective_id !== id);
          setPeerObjectives(peers);
        })
        .catch(() => undefined);
    }
  }, [detail, id]);

  async function submitCheckin(e: React.FormEvent) {
    e.preventDefault();
    if (!showCheckinForm) return;
    setSubmitting(true);
    try {
      await fetch(`${BACKEND}/okrs/key-results/${showCheckinForm}/checkins`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_value: checkinForm.current_value ? parseFloat(checkinForm.current_value) : null,
          confidence: parseFloat(checkinForm.confidence),
          blockers: checkinForm.blockers,
          decisions_needed: checkinForm.decisions_needed,
          narrative_update: checkinForm.narrative_update,
          next_steps: checkinForm.next_steps,
          org_id: "org-1",
          parent_checkin_id: checkinParentId ?? null,
        }),
      });
      setShowCheckinForm(null);
      setCheckinParentId(null);
      setCheckinForm({ current_value: "", confidence: "0.7", blockers: "", decisions_needed: "", narrative_update: "", next_steps: "" });
      loadDetail();
    } catch { /* ignore */ }
    setSubmitting(false);
  }

  /** Build version chains from a flat list of checkins.
   *  A chain is headed by the "latest" record — i.e. the one no other
   *  checkin points to as its parent. All predecessors form the history. */
  function buildCheckinChains(all: Checkin[]): CheckinChain[] {
    const byId = new Map(all.map(c => [c.checkin_id, c]));
    const supersededIds = new Set(
      all.filter(c => c.parent_checkin_id).map(c => c.parent_checkin_id as string)
    );
    const heads = all.filter(c => !supersededIds.has(c.checkin_id));
    return heads.map(head => {
      const history: Checkin[] = [];
      let cur = head;
      while (cur.parent_checkin_id) {
        const prev = byId.get(cur.parent_checkin_id);
        if (!prev) break;
        history.push(prev);
        cur = prev;
      }
      return { latest: head, history };
    });
  }

  async function submitKR(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await fetch(`${BACKEND}/okrs/objectives/${id}/key-results`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: krForm.title, kr_type: krForm.kr_type,
          baseline_value: krForm.baseline_value ? parseFloat(krForm.baseline_value) : null,
          target_value: krForm.target_value ? parseFloat(krForm.target_value) : null,
          unit: krForm.unit, direction: krForm.direction,
          description: krForm.description, owner_user_id: "user-1", org_id: "org-1",
        }),
      });
      setShowKrForm(false);
      setKrForm({ title: "", kr_type: "metric", baseline_value: "", target_value: "", unit: "", direction: "increase", description: "" });
      loadDetail();
    } catch { /* ignore */ }
    setSubmitting(false);
  }

  async function submitEdit(e: React.FormEvent) {
    e.preventDefault();
    setEditError(null);
    if (!editForm.title.trim()) return setEditError("Title is required");
    setSubmitting(true);
    try {
      const body: Record<string, string | null> = {
        title: editForm.title.trim(),
        description: editForm.description,
        rationale: editForm.rationale,
        objective_type: editForm.objective_type,
        status: editForm.status,
        owner_user_id: editForm.owner_user_id || "user-1",
        sponsor_user_id: editForm.sponsor_user_id || null,
        visibility: editForm.visibility,
        parent_objective_id: editForm.parent_objective_id || null,
      };
      const res = await fetch(`${BACKEND}/okrs/objectives/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(await res.text());
      setShowEditForm(false);
      loadDetail();
    } catch (err) {
      setEditError(String(err));
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <PageShell title="OKR Detail"><p>Loading…</p></PageShell>;
  if (!detail) return <PageShell title="OKR Detail"><p>Objective not found.</p></PageShell>;

  const krs: KeyResult[] = (detail as { key_results?: KeyResult[] }).key_results ?? [];
  const checkins: Checkin[] = (detail as { checkins?: Checkin[] }).checkins ?? [];
  const initiatives: Initiative[] = (detail as { initiatives?: Initiative[] }).initiatives ?? [];
  const dependencies: Dependency[] = (detail as { dependencies?: Dependency[] }).dependencies ?? [];

  return (
    <PageShell
      title={detail.title}
      subtitle={`${detail.objective_type} · ${detail.status}`}
      breadcrumbs={[{ label: "OKRs", href: "/okrs" }, { label: "Detail" }]}
      headerActions={
        <div style={{ display: "flex", gap: "var(--space-1)" }}>
          <button className="btn btn-primary" onClick={() => setShowEditForm(true)}>
            ✏ Edit Objective
          </button>
          <a href={`${BACKEND}/okrs/objectives/${id}/export`} className="btn" target="_blank" rel="noopener noreferrer">Export</a>
        </div>
      }
    >
      {/* Header stats */}
      <div className="card" style={{ padding: "var(--space-3)", marginBottom: "var(--space-3)" }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: "var(--space-3)", flexWrap: "wrap" }}>
          {/* Type + health */}
          <div style={{ display: "flex", gap: "var(--space-1)", alignItems: "center" }}>
            <span style={{ background: TYPE_BG[detail.objective_type] ?? "#888", color: "#fff", borderRadius: "var(--radius-s)", padding: "2px 8px", fontSize: "0.75rem", fontWeight: 600 }}>
              {detail.objective_type}
            </span>
            <span style={{ color: HEALTH_COLOR[detail.health_current], fontWeight: 700, fontSize: "1.1rem" }}>●</span>
            <span style={{ fontSize: "0.8rem", color: "var(--text-muted, #888)" }}>{detail.health_current}</span>
          </div>
          {/* Score */}
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "var(--accent)" }}>{Math.round((detail.confidence_current ?? 0) * 100)}%</div>
            <div style={{ fontSize: "0.7rem", color: "var(--text-muted, #888)" }}>Confidence</div>
          </div>
          {/* KR count */}
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: "1.5rem", fontWeight: 700 }}>{krs.length}</div>
            <div style={{ fontSize: "0.7rem", color: "var(--text-muted, #888)" }}>Key Results</div>
          </div>
          {/* Quality score */}
          {detail.quality_score && (
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: "1.5rem", fontWeight: 700, color: detail.quality_score >= 7 ? "#22c55e" : detail.quality_score >= 4 ? "#eab308" : "#ef4444" }}>
                {detail.quality_score}/10
              </div>
              <div style={{ fontSize: "0.7rem", color: "var(--text-muted, #888)" }}>Quality</div>
            </div>
          )}
          {/* Owner / Period metadata */}
          <div style={{ marginLeft: "auto", textAlign: "right", fontSize: "0.8rem", color: "var(--text-muted, #888)" }}>
            {detail.owner_user_id && <div>Owner: <strong>{detail.owner_user_id}</strong></div>}
            {detail.sponsor_user_id && <div>Sponsor: <strong>{detail.sponsor_user_id}</strong></div>}
            {detail.org_node_id && <div>Team: <strong>{detail.org_node_id}</strong></div>}
          </div>
        </div>
        {detail.description && <p style={{ marginTop: "var(--space-2)", color: "var(--text-muted, #888)", fontSize: "0.875rem" }}>{detail.description}</p>}
        {detail.rationale && <p style={{ marginTop: 4, fontSize: "0.8rem", fontStyle: "italic", color: "var(--text-muted, #888)" }}>Rationale: {detail.rationale}</p>}
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 0, marginBottom: "var(--space-3)", borderBottom: "1px solid var(--border)" }}>
        {[
          { id: "key_results", label: `Key Results (${krs.length})` },
          { id: "checkins", label: `Check-ins (${checkins.length})` },
          { id: "initiatives", label: `Initiatives (${initiatives.length})` },
          { id: "dependencies", label: `Dependencies (${dependencies.length})` },
        ].map(tab => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)}
            style={{ padding: "8px 16px", border: "none", background: "none", cursor: "pointer", fontWeight: activeTab === tab.id ? 600 : 400, borderBottom: activeTab === tab.id ? "2px solid var(--accent)" : "2px solid transparent", color: activeTab === tab.id ? "var(--accent)" : "var(--text-muted, #888)", fontSize: "0.875rem" }}>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Key Results */}
      {activeTab === "key_results" && (
        <div>
          <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: "var(--space-2)" }}>
            <button className="btn btn-primary" onClick={() => setShowKrForm(true)}>+ Add Key Result</button>
          </div>
          {krs.length === 0 ? (
            <div className="card" style={{ padding: "var(--space-3)", textAlign: "center", color: "var(--text-muted, #888)" }}>No key results yet. Add your first KR to make this objective measurable.</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
              {krs.map(kr => (
                <div key={kr.kr_id} className="card" style={{ padding: "var(--space-3)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "var(--space-2)", marginBottom: "var(--space-2)" }}>
                    <div>
                      <span style={{ background: KR_TYPE_BG[kr.kr_type] ?? "#888", color: "#fff", borderRadius: "var(--radius-s)", padding: "1px 6px", fontSize: "0.65rem", fontWeight: 600, marginRight: 6 }}>{kr.kr_type}</span>
                      <span style={{ fontWeight: 500 }}>{kr.title}</span>
                    </div>
                    <button className="btn" style={{ fontSize: "0.75rem", padding: "4px 10px" }} onClick={() => setShowCheckinForm(kr.kr_id)}>Check-in</button>
                  </div>
                  {/* Score bar */}
                  <div style={{ marginBottom: "var(--space-1)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", marginBottom: 3 }}>
                      <span style={{ color: "var(--text-muted, #888)" }}>Score</span>
                      <span style={{ fontWeight: 600, color: HEALTH_COLOR[kr.health_current] }}>{Math.round((kr.score_current ?? 0) * 100)}%</span>
                    </div>
                    <div style={{ height: 6, background: "var(--border)", borderRadius: 3, overflow: "hidden" }}>
                      <div style={{ height: "100%", width: `${Math.round((kr.score_current ?? 0) * 100)}%`, background: HEALTH_COLOR[kr.health_current], borderRadius: 3, transition: "width 0.3s" }} />
                    </div>
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted, #888)", display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
                    {kr.baseline_value != null && <span>Baseline: {kr.baseline_value}{kr.unit}</span>}
                    {kr.current_value != null && <span>Current: {kr.current_value}{kr.unit}</span>}
                    {kr.target_value != null && <span>Target: {kr.target_value}{kr.unit}</span>}
                    <span>Confidence: {Math.round((kr.confidence_current ?? 0) * 100)}%</span>
                    {kr.due_date && <span>Due: {kr.due_date}</span>}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Add KR form */}
          {showKrForm && (
            <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
              <div className="card" style={{ width: 500, maxHeight: "90vh", overflow: "auto", padding: "var(--space-4)" }}>
                <h3 style={{ marginBottom: "var(--space-3)" }}>Add Key Result</h3>
                <form onSubmit={submitKR} style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
                  <div><label style={{ display: "block", marginBottom: 4, fontSize: "0.875rem" }}>Title *</label>
                    <input className="form-input" style={{ width: "100%" }} type="text" placeholder="Grow NPS from 42 to 65" value={krForm.title} onChange={e => setKrForm(f => ({ ...f, title: e.target.value }))} required /></div>
                  <div><label style={{ display: "block", marginBottom: 4, fontSize: "0.875rem" }}>Type</label>
                    <select className="form-input" style={{ width: "100%" }} value={krForm.kr_type} onChange={e => setKrForm(f => ({ ...f, kr_type: e.target.value }))}>
                      <option value="metric">Metric — measured with a number</option>
                      <option value="milestone">Milestone — defined rubric (0 / 0.3 / 0.7 / 1.0)</option>
                      <option value="binary">Binary — done or not done</option>
                    </select></div>
                  {krForm.kr_type === "metric" && (
                    <>
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--space-1)" }}>
                        <div><label style={{ display: "block", marginBottom: 4, fontSize: "0.875rem" }}>Baseline</label>
                          <input className="form-input" style={{ width: "100%" }} type="number" placeholder="42" value={krForm.baseline_value} onChange={e => setKrForm(f => ({ ...f, baseline_value: e.target.value }))} /></div>
                        <div><label style={{ display: "block", marginBottom: 4, fontSize: "0.875rem" }}>Target</label>
                          <input className="form-input" style={{ width: "100%" }} type="number" placeholder="65" value={krForm.target_value} onChange={e => setKrForm(f => ({ ...f, target_value: e.target.value }))} /></div>
                        <div><label style={{ display: "block", marginBottom: 4, fontSize: "0.875rem" }}>Unit</label>
                          <input className="form-input" style={{ width: "100%" }} type="text" placeholder="NPS pts" value={krForm.unit} onChange={e => setKrForm(f => ({ ...f, unit: e.target.value }))} /></div>
                      </div>
                      <div><label style={{ display: "block", marginBottom: 4, fontSize: "0.875rem" }}>Direction</label>
                        <select className="form-input" style={{ width: "100%" }} value={krForm.direction} onChange={e => setKrForm(f => ({ ...f, direction: e.target.value }))}>
                          <option value="increase">Increase</option>
                          <option value="decrease">Decrease</option>
                          <option value="maintain">Maintain</option>
                          <option value="achieve">Achieve</option>
                        </select></div>
                    </>
                  )}
                  {krForm.kr_type === "binary" && (
                    <div><label style={{ display: "block", marginBottom: 4, fontSize: "0.875rem" }}>Acceptance Criteria *</label>
                      <textarea className="form-input" style={{ width: "100%", minHeight: 60 }} placeholder="Describe exactly what conditions make this KR complete" value={krForm.description} onChange={e => setKrForm(f => ({ ...f, description: e.target.value }))} required /></div>
                  )}
                  <div style={{ display: "flex", gap: "var(--space-2)", justifyContent: "flex-end" }}>
                    <button type="button" className="btn" onClick={() => setShowKrForm(false)}>Cancel</button>
                    <button type="submit" className="btn btn-primary" disabled={submitting}>{submitting ? "Adding…" : "Add KR"}</button>
                  </div>
                </form>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Check-ins */}
      {activeTab === "checkins" && (
        <div>
          {checkins.length === 0 ? (
            <div className="card" style={{ padding: "var(--space-3)", textAlign: "center", color: "var(--text-muted, #888)" }}>No check-ins yet. Use the Check-in button on a Key Result.</div>
          ) : (() => {
            const chains = buildCheckinChains(checkins);
            return (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
                {chains.map(chain => {
                  const c = chain.latest;
                  const isKR = c.object_type === "key_result";
                  const linkedKR = isKR ? krs.find(k => k.kr_id === c.object_id) : null;
                  const histExpanded = expandedHistory.has(c.checkin_id);

                  return (
                    <div key={c.checkin_id} className="card" style={{ padding: "var(--space-3)" }}>
                      {/* Source label + Update button */}
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "var(--space-1)" }}>
                        <div>
                          {isKR && (
                            <>
                              <span style={{ background: KR_TYPE_BG[linkedKR?.kr_type ?? "metric"] ?? "#888", color: "#fff", borderRadius: "var(--radius-s)", padding: "1px 6px", fontSize: "0.65rem", fontWeight: 600, marginRight: 6 }}>
                                {linkedKR?.kr_type ?? "kr"}
                              </span>
                              <span style={{ fontSize: "0.78rem", color: "var(--text-muted,#888)" }}>
                                {linkedKR?.title ?? "KR check-in"}
                              </span>
                            </>
                          )}
                          {!isKR && (
                            <span style={{ fontSize: "0.78rem", color: "var(--text-muted,#888)", fontStyle: "italic" }}>Objective check-in</span>
                          )}
                        </div>
                        {/* Update button — only for KR check-ins (we can re-submit against a KR) */}
                        {isKR && c.object_id && (
                          <button
                            className="btn"
                            style={{ fontSize: "0.7rem", padding: "3px 9px" }}
                            onClick={() => {
                              setCheckinParentId(c.checkin_id);
                              setCheckinForm({
                                current_value: c.current_value != null ? String(c.current_value) : "",
                                confidence: c.confidence_snapshot != null ? String(c.confidence_snapshot) : "0.7",
                                blockers: c.blockers ?? "",
                                decisions_needed: c.decisions_needed ?? "",
                                narrative_update: c.narrative_update ?? "",
                                next_steps: c.next_steps ?? "",
                              });
                              setShowCheckinForm(c.object_id);
                            }}
                          >
                            ↻ Update
                          </button>
                        )}
                      </div>

                      {/* Latest check-in values */}
                      <div style={{ display: "flex", gap: "var(--space-2)", marginBottom: "var(--space-2)", fontSize: "0.8rem", color: "var(--text-muted, #888)", flexWrap: "wrap" }}>
                        <span>{c.checkin_date || c.created_at?.slice(0, 10)}</span>
                        <span>by {c.user_id}</span>
                        {c.current_value != null && <span>Value: <strong>{c.current_value}</strong></span>}
                        {c.confidence_snapshot != null && <span>Confidence: <strong>{Math.round(c.confidence_snapshot * 100)}%</strong></span>}
                        {c.score_snapshot != null && <span>Score: <strong>{Math.round(c.score_snapshot * 100)}%</strong></span>}
                      </div>
                      {c.narrative_update && <p style={{ fontSize: "0.875rem", marginBottom: "var(--space-1)" }}>{c.narrative_update}</p>}
                      {c.blockers && <p style={{ fontSize: "0.8rem", color: "#ef4444" }}>⚠ Blockers: {c.blockers}</p>}
                      {c.decisions_needed && <p style={{ fontSize: "0.8rem", color: "#eab308" }}>❓ Decisions needed: {c.decisions_needed}</p>}
                      {c.next_steps && <p style={{ fontSize: "0.8rem", color: "var(--text-muted, #888)" }}>→ Next: {c.next_steps}</p>}

                      {/* History section — collapsible */}
                      {chain.history.length > 0 && (
                        <div style={{ marginTop: "var(--space-2)", borderTop: "1px solid var(--border)", paddingTop: "var(--space-1)" }}>
                          <button
                            style={{ background: "none", border: "none", cursor: "pointer", fontSize: "0.75rem", color: "var(--text-muted,#888)", padding: "2px 0", display: "flex", alignItems: "center", gap: 4 }}
                            onClick={() => setExpandedHistory(prev => {
                              const next = new Set(prev);
                              next.has(c.checkin_id) ? next.delete(c.checkin_id) : next.add(c.checkin_id);
                              return next;
                            })}
                          >
                            {histExpanded ? "▾" : "▸"} History ({chain.history.length} version{chain.history.length > 1 ? "s" : ""})
                          </button>
                          {histExpanded && (
                            <div style={{ marginTop: "var(--space-1)", display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
                              {chain.history.map((h, idx) => (
                                <div key={h.checkin_id} style={{ padding: "var(--space-1) var(--space-2)", background: "var(--surface, #f9f9f9)", borderRadius: "var(--radius-s)", opacity: 0.7, borderLeft: "3px solid var(--border)" }}>
                                  <div style={{ display: "flex", gap: "var(--space-2)", fontSize: "0.75rem", color: "var(--text-muted,#888)", flexWrap: "wrap", marginBottom: 2 }}>
                                    <span style={{ background: "var(--border)", borderRadius: 3, padding: "0 5px", fontSize: "0.65rem" }}>superseded v{chain.history.length - idx}</span>
                                    <span>{h.checkin_date || h.created_at?.slice(0, 10)}</span>
                                    {h.current_value != null && <span>Value: {h.current_value}</span>}
                                    {h.confidence_snapshot != null && <span>Confidence: {Math.round(h.confidence_snapshot * 100)}%</span>}
                                  </div>
                                  {h.narrative_update && <p style={{ fontSize: "0.8rem", margin: 0 }}>{h.narrative_update}</p>}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            );
          })()}
        </div>
      )}

      {/* Initiatives */}
      {activeTab === "initiatives" && (
        <div>
          {initiatives.length === 0 ? (
            <div className="card" style={{ padding: "var(--space-3)", textAlign: "center", color: "var(--text-muted, #888)" }}>No initiatives linked to this objective.</div>
          ) : (
            <table className="data-table" style={{ width: "100%" }}>
              <thead><tr><th>Title</th><th>Status</th><th>Owner</th><th>External Ref</th></tr></thead>
              <tbody>
                {initiatives.map(i => (
                  <tr key={i.initiative_id}>
                    <td>{i.title}</td>
                    <td><span className="badge">{i.status.replace("_", " ")}</span></td>
                    <td>{i.owner_user_id}</td>
                    <td>{i.external_system_ref ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Dependencies */}
      {activeTab === "dependencies" && (
        <div>
          {dependencies.length === 0 ? (
            <div className="card" style={{ padding: "var(--space-3)", textAlign: "center", color: "var(--text-muted, #888)" }}>No dependencies defined for this objective.</div>
          ) : (
            <table className="data-table" style={{ width: "100%" }}>
              <thead><tr><th>Direction</th><th>Type</th><th>Object</th><th>Severity</th></tr></thead>
              <tbody>
                {dependencies.map(d => {
                  const isSource = d.source_object_id === id;
                  return (
                    <tr key={d.dependency_id}>
                      <td style={{ fontSize: "0.8rem" }}>{isSource ? "→ outgoing" : "← incoming"}</td>
                      <td><span className="badge">{d.dependency_type.replace("_", " ")}</span></td>
                      <td style={{ fontSize: "0.8rem" }}>{isSource ? `${d.target_object_type} ${d.target_object_id.slice(0, 12)}…` : `${d.source_object_type} ${d.source_object_id.slice(0, 12)}…`}</td>
                      <td><span style={{ color: d.severity === "critical" ? "#ef4444" : d.severity === "high" ? "#f97316" : "var(--text-muted, #888)", fontSize: "0.8rem" }}>{d.severity}</span></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ── Edit Objective Modal ────────────────────────────────────────── */}
      {showEditForm && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
          <div className="card" style={{ width: 540, maxHeight: "92vh", overflow: "auto", padding: "var(--space-4)" }}>
            <h3 style={{ margin: "0 0 var(--space-3)", fontSize: "1rem", fontWeight: 600 }}>Edit Objective</h3>
            <form onSubmit={submitEdit} style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>

              <label style={{ fontSize: "0.875rem", fontWeight: 500 }}>
                Title <span style={{ color: "#dc2626" }}>*</span>
                <input
                  className="form-input"
                  style={{ display: "block", width: "100%", marginTop: 4 }}
                  value={editForm.title}
                  onChange={e => setEditForm(f => ({ ...f, title: e.target.value }))}
                  placeholder="Outcome-focused objective title"
                  autoFocus
                />
              </label>

              <label style={{ fontSize: "0.875rem", fontWeight: 500 }}>
                Description
                <textarea
                  className="form-input"
                  style={{ display: "block", width: "100%", marginTop: 4, minHeight: 72, resize: "vertical" }}
                  value={editForm.description}
                  onChange={e => setEditForm(f => ({ ...f, description: e.target.value }))}
                  placeholder="What does success look like for this objective?"
                />
              </label>

              <label style={{ fontSize: "0.875rem", fontWeight: 500 }}>
                Rationale / Why
                <textarea
                  className="form-input"
                  style={{ display: "block", width: "100%", marginTop: 4, minHeight: 56, resize: "vertical" }}
                  value={editForm.rationale}
                  onChange={e => setEditForm(f => ({ ...f, rationale: e.target.value }))}
                  placeholder="Why does this objective matter this quarter?"
                />
              </label>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-2)" }}>
                <label style={{ fontSize: "0.875rem", fontWeight: 500 }}>
                  Type
                  <select className="form-input" style={{ display: "block", width: "100%", marginTop: 4 }} value={editForm.objective_type} onChange={e => setEditForm(f => ({ ...f, objective_type: e.target.value }))}>
                    <option value="committed">Committed</option>
                    <option value="aspirational">Aspirational</option>
                  </select>
                </label>

                <label style={{ fontSize: "0.875rem", fontWeight: 500 }}>
                  Status
                  <select className="form-input" style={{ display: "block", width: "100%", marginTop: 4 }} value={editForm.status} onChange={e => setEditForm(f => ({ ...f, status: e.target.value }))}>
                    <option value="draft">Draft</option>
                    <option value="active">Active</option>
                    <option value="achieved">Achieved</option>
                    <option value="cancelled">Cancelled</option>
                  </select>
                </label>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-2)" }}>
                <label style={{ fontSize: "0.875rem", fontWeight: 500 }}>
                  Owner User ID
                  <input className="form-input" style={{ display: "block", width: "100%", marginTop: 4 }} value={editForm.owner_user_id} onChange={e => setEditForm(f => ({ ...f, owner_user_id: e.target.value }))} placeholder="user-1" />
                </label>
                <label style={{ fontSize: "0.875rem", fontWeight: 500 }}>
                  Sponsor User ID <span style={{ color: "var(--text-muted, #888)", fontWeight: 400 }}>(optional)</span>
                  <input className="form-input" style={{ display: "block", width: "100%", marginTop: 4 }} value={editForm.sponsor_user_id} onChange={e => setEditForm(f => ({ ...f, sponsor_user_id: e.target.value }))} placeholder="e.g. user-2" />
                </label>
              </div>

              <label style={{ fontSize: "0.875rem", fontWeight: 500 }}>
                Visibility
                <select className="form-input" style={{ display: "block", width: "100%", marginTop: 4 }} value={editForm.visibility} onChange={e => setEditForm(f => ({ ...f, visibility: e.target.value }))}>
                  <option value="team">Team — visible to team members only</option>
                  <option value="org">Org — visible across the organization</option>
                  <option value="public">Public — visible to all</option>
                </select>
              </label>

              <label style={{ fontSize: "0.875rem", fontWeight: 500 }}>
                Parent Objective <span style={{ color: "var(--text-muted, #888)", fontWeight: 400 }}>(optional — for cascade alignment)</span>
                <select
                  className="form-input"
                  style={{ display: "block", width: "100%", marginTop: 4 }}
                  value={editForm.parent_objective_id}
                  onChange={e => setEditForm(f => ({ ...f, parent_objective_id: e.target.value }))}
                >
                  <option value="">— None —</option>
                  {peerObjectives.map(o => (
                    <option key={o.objective_id} value={o.objective_id}>
                      {o.title.length > 55 ? o.title.slice(0, 53) + "…" : o.title}
                    </option>
                  ))}
                </select>
              </label>

              {editError && <p style={{ color: "#dc2626", fontSize: "0.8rem", margin: 0 }}>{editError}</p>}

              <div style={{ display: "flex", gap: "var(--space-2)", justifyContent: "flex-end", marginTop: "var(--space-2)" }}>
                <button type="button" className="btn" onClick={() => { setShowEditForm(false); setEditError(null); }} disabled={submitting}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? "Saving…" : "Save Changes"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Check-in modal ─────────────────────────────────────────────── */}
      {showCheckinForm && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
          <div className="card" style={{ width: 500, maxHeight: "90vh", overflow: "auto", padding: "var(--space-4)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
              <h3 style={{ margin: 0 }}>{checkinParentId ? "Update Check-in" : "Weekly Check-in"}</h3>
              {checkinParentId && (
                <span style={{ fontSize: "0.7rem", background: "#fef3c7", color: "#92400e", borderRadius: "var(--radius-s)", padding: "2px 8px" }}>
                  Creates a new version · original preserved
                </span>
              )}
            </div>
            <form onSubmit={submitCheckin} style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-1)" }}>
                <div><label style={{ display: "block", marginBottom: 4, fontSize: "0.875rem" }}>Current Value</label>
                  <input className="form-input" style={{ width: "100%" }} type="number" step="any" placeholder="e.g. 48" value={checkinForm.current_value} onChange={e => setCheckinForm(f => ({ ...f, current_value: e.target.value }))} /></div>
                <div><label style={{ display: "block", marginBottom: 4, fontSize: "0.875rem" }}>Confidence (0–1)</label>
                  <input className="form-input" style={{ width: "100%" }} type="number" min="0" max="1" step="0.05" value={checkinForm.confidence} onChange={e => setCheckinForm(f => ({ ...f, confidence: e.target.value }))} /></div>
              </div>
              <div><label style={{ display: "block", marginBottom: 4, fontSize: "0.875rem" }}>Narrative Update</label>
                <textarea className="form-input" style={{ width: "100%", minHeight: 60 }} placeholder="What happened this week? Why is the number where it is?" value={checkinForm.narrative_update} onChange={e => setCheckinForm(f => ({ ...f, narrative_update: e.target.value }))} /></div>
              <div><label style={{ display: "block", marginBottom: 4, fontSize: "0.875rem" }}>Blockers</label>
                <input className="form-input" style={{ width: "100%" }} type="text" placeholder="What's in the way?" value={checkinForm.blockers} onChange={e => setCheckinForm(f => ({ ...f, blockers: e.target.value }))} /></div>
              <div><label style={{ display: "block", marginBottom: 4, fontSize: "0.875rem" }}>Decisions Needed</label>
                <input className="form-input" style={{ width: "100%" }} type="text" placeholder="What decisions need to be made?" value={checkinForm.decisions_needed} onChange={e => setCheckinForm(f => ({ ...f, decisions_needed: e.target.value }))} /></div>
              <div><label style={{ display: "block", marginBottom: 4, fontSize: "0.875rem" }}>Next Steps</label>
                <input className="form-input" style={{ width: "100%" }} type="text" value={checkinForm.next_steps} onChange={e => setCheckinForm(f => ({ ...f, next_steps: e.target.value }))} /></div>
              <div style={{ display: "flex", gap: "var(--space-2)", justifyContent: "flex-end" }}>
                <button type="button" className="btn" onClick={() => { setShowCheckinForm(null); setCheckinParentId(null); setCheckinForm({ current_value: "", confidence: "0.7", blockers: "", decisions_needed: "", narrative_update: "", next_steps: "" }); }}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>{submitting ? "Submitting…" : checkinParentId ? "Save Update" : "Submit Check-in"}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </PageShell>
  );
}
