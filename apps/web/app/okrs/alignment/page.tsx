"use client";

import React, { useEffect, useState, useRef, useCallback } from "react";
import { PageShell } from "@/components/page-shell";

const BACKEND = process.env.NEXT_PUBLIC_FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000";

interface AlignmentNode {
  id: string;
  label: string;
  type: "objective" | "org_node";
  node_type?: string; // company/team/department/etc
  health?: string;
  score?: number;
  objective_type?: string;
  org_node_id?: string;
  parent_id?: string;
}

interface AlignmentEdge {
  source: string;
  target: string;
  edge_type: "parent_child" | "contributed" | "shared" | "depends_on";
}

interface AlignmentGraph {
  nodes: AlignmentNode[];
  edges: AlignmentEdge[];
  orphans?: string[];
  over_cascaded?: string[];
  missing_links?: string[];
  duplicates?: string[];
  overloaded_teams?: string[];
}

interface ObjDetail {
  objective_id: string;
  title: string;
  objective_type: string;
  health_current: string;
  confidence_current: number;
  org_node_id: string;
  parent_objective_id?: string;
}

const HEALTH_COLOR: Record<string, string> = { green: "#16a34a", yellow: "#ca8a04", red: "#dc2626" };
const EDGE_COLOR: Record<string, string> = {
  parent_child: "#6b7280",
  contributed: "#3b82f6",
  shared: "#8b5cf6",
  depends_on: "#f59e0b",
};
const EDGE_DASH: Record<string, string> = {
  parent_child: "none",
  contributed: "5,3",
  shared: "3,3",
  depends_on: "8,4",
};

function buildTreeFromObjectives(objectives: ObjDetail[]): AlignmentGraph {
  const nodes: AlignmentNode[] = objectives.map(o => ({
    id: o.objective_id,
    label: o.title,
    type: "objective",
    health: o.health_current,
    objective_type: o.objective_type,
    org_node_id: o.org_node_id,
    parent_id: o.parent_objective_id,
  }));
  const edges: AlignmentEdge[] = objectives
    .filter(o => o.parent_objective_id)
    .map(o => ({ source: o.parent_objective_id!, target: o.objective_id, edge_type: "parent_child" }));
  return { nodes, edges };
}

// Simple force-directed layout (deterministic)
function layoutNodes(nodes: AlignmentNode[], edges: AlignmentEdge[], width: number, height: number) {
  const pos: Record<string, { x: number; y: number }> = {};
  if (nodes.length === 0) return pos;

  // Find roots (no parent in the graph)
  const hasParent = new Set(edges.filter(e => e.edge_type === "parent_child").map(e => e.target));
  const roots = nodes.filter(n => !hasParent.has(n.id));
  const childrenMap: Record<string, string[]> = {};
  edges.filter(e => e.edge_type === "parent_child").forEach(e => {
    if (!childrenMap[e.source]) childrenMap[e.source] = [];
    childrenMap[e.source].push(e.target);
  });

  let y = 60;
  const levelHeight = Math.min(120, (height - 80) / Math.max(1, roots.length));

  function placeSubtree(nodeId: string, minX: number, maxX: number, currentY: number): void {
    pos[nodeId] = { x: (minX + maxX) / 2, y: currentY };
    const children = childrenMap[nodeId] ?? [];
    if (children.length === 0) return;
    const segW = (maxX - minX) / children.length;
    children.forEach((childId, i) => {
      placeSubtree(childId, minX + i * segW, minX + (i + 1) * segW, currentY + levelHeight);
    });
  }

  const rootSegW = (width - 80) / Math.max(1, roots.length);
  roots.forEach((root, i) => {
    placeSubtree(root.id, 40 + i * rootSegW, 40 + (i + 1) * rootSegW, y);
  });

  // Place orphaned nodes at bottom
  nodes.filter(n => !pos[n.id]).forEach((n, i) => {
    pos[n.id] = { x: 60 + (i * 120) % (width - 80), y: height - 60 };
  });

  return pos;
}

export default function AlignmentGraphPage() {
  const [objectives, setObjectives] = useState<ObjDetail[]>([]);
  const [graph, setGraph] = useState<AlignmentGraph | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<ObjDetail | null>(null);
  const [filter, setFilter] = useState<string>("all");
  const [periods, setPeriods] = useState<Array<{ period_id: string; name: string }>>([]);
  const [periodId, setPeriodId] = useState("");
  const svgRef = useRef<SVGSVGElement>(null);
  const [svgSize] = useState({ width: 900, height: 520 });

  useEffect(() => {
    fetch(`${BACKEND}/okrs/periods?org_id=org-1`)
      .then(r => r.json())
      .then(d => {
        const ps = d.periods ?? d ?? [];
        setPeriods(ps);
        const active = ps.find((p: { status: string }) => p.status === "active");
        if (active) setPeriodId(active.period_id);
        else if (ps.length > 0) setPeriodId(ps[0].period_id);
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!periodId) return;
    setLoading(true);
    Promise.all([
      fetch(`${BACKEND}/okrs/objectives?period_id=${periodId}&org_id=org-1`).then(r => r.json()),
      fetch(`${BACKEND}/okrs/alignment-graph?period_id=${periodId}&org_id=org-1`).then(r => r.json()).catch(() => null),
    ])
      .then(([objData, graphData]) => {
        const objs: ObjDetail[] = objData.objectives ?? objData ?? [];
        setObjectives(objs);
        if (graphData && graphData.nodes) {
          setGraph(graphData);
        } else {
          setGraph(buildTreeFromObjectives(objs));
        }
        setLoading(false);
      })
      .catch(e => { setError(String(e)); setLoading(false); });
  }, [periodId]);

  const filteredEdges = graph?.edges.filter(e => filter === "all" || e.edge_type === filter) ?? [];
  const nodePos = graph ? layoutNodes(graph.nodes, filteredEdges, svgSize.width, svgSize.height) : {};

  const objMap = Object.fromEntries(objectives.map(o => [o.objective_id, o]));

  const handleNodeClick = useCallback((nodeId: string) => {
    setSelected(objMap[nodeId] ?? null);
  }, [objMap]);

  const orphans = graph?.orphans ?? [];
  const overloaded = graph?.overloaded_teams ?? [];
  const missing = graph?.missing_links ?? [];

  return (
    <PageShell
      title="Alignment Graph"
      subtitle="Visual map of objective hierarchy, contributors, and cross-team dependencies"
      breadcrumbs={[{ label: "OKRs", href: "/okrs" }, { label: "Alignment Graph" }]}
    >
      {/* Controls bar */}
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-2)", flexWrap: "wrap" }}>
        <label style={{ fontSize: "0.8rem", color: "var(--text-muted, #888)" }}>Period</label>
        <select value={periodId} onChange={e => setPeriodId(e.target.value)} className="form-input" style={{ width: 180 }}>
          {periods.map(p => <option key={p.period_id} value={p.period_id}>{p.name}</option>)}
        </select>

        <label style={{ fontSize: "0.8rem", color: "var(--text-muted, #888)", marginLeft: "var(--space-2)" }}>Show</label>
        {["all", "parent_child", "contributed", "shared", "depends_on"].map(f => (
          <button
            key={f}
            className="btn"
            onClick={() => setFilter(f)}
            style={{
              padding: "3px 10px",
              fontSize: "0.75rem",
              background: filter === f ? "var(--accent)" : "var(--surface)",
              color: filter === f ? "#fff" : "inherit",
              borderColor: filter === f ? "var(--accent)" : "var(--border)"
            }}
          >
            {f === "all" ? "All" : f.replace("_", " ")}
          </button>
        ))}

        {/* Legend */}
        <div style={{ marginLeft: "auto", display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
          {Object.entries(EDGE_COLOR).map(([type, color]) => (
            <span key={type} style={{ fontSize: "0.7rem", display: "flex", alignItems: "center", gap: 4, color: "var(--text-muted, #888)" }}>
              <svg width={20} height={10}>
                <line x1={0} y1={5} x2={20} y2={5} stroke={color} strokeWidth={2} strokeDasharray={EDGE_DASH[type]} />
              </svg>
              {type.replace("_", " ")}
            </span>
          ))}
        </div>
      </div>

      {loading && <p style={{ color: "var(--text-muted, #888)" }}>Building alignment graph…</p>}
      {error && <p style={{ color: "var(--danger, #dc2626)" }}>{error}</p>}

      {!loading && !error && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 280px", gap: "var(--space-3)", alignItems: "start" }}>
          {/* SVG canvas */}
          <div className="card" style={{ padding: 0, overflow: "hidden" }}>
            {(graph?.nodes.length ?? 0) === 0 ? (
              <div style={{ padding: "var(--space-4)", color: "var(--text-muted, #888)", textAlign: "center" }}>
                No objectives to visualize for this period.
              </div>
            ) : (
              <svg
                ref={svgRef}
                width="100%"
                viewBox={`0 0 ${svgSize.width} ${svgSize.height}`}
                style={{ display: "block", background: "var(--bg)" }}
              >
                <defs>
                  <marker id="arrow" viewBox="0 0 10 10" refX={9} refY={5} markerWidth={6} markerHeight={6} orient="auto-start-reverse">
                    <path d="M 0 0 L 10 5 L 0 10 z" fill="#9ca3af" />
                  </marker>
                </defs>

                {/* Edges */}
                {filteredEdges.map((edge, i) => {
                  const s = nodePos[edge.source];
                  const t = nodePos[edge.target];
                  if (!s || !t) return null;
                  const color = EDGE_COLOR[edge.edge_type] ?? "#9ca3af";
                  const dash = EDGE_DASH[edge.edge_type] ?? "none";
                  return (
                    <line
                      key={i}
                      x1={s.x} y1={s.y + 16}
                      x2={t.x} y2={t.y - 16}
                      stroke={color}
                      strokeWidth={1.5}
                      strokeDasharray={dash}
                      markerEnd="url(#arrow)"
                      opacity={0.7}
                    />
                  );
                })}

                {/* Nodes */}
                {graph?.nodes.map(node => {
                  const p = nodePos[node.id];
                  if (!p) return null;
                  const health = node.health ?? "yellow";
                  const color = HEALTH_COLOR[health] ?? "#ca8a04";
                  const isSelected = selected?.objective_id === node.id;
                  const label = node.label.length > 28 ? node.label.slice(0, 26) + "…" : node.label;
                  return (
                    <g key={node.id} onClick={() => handleNodeClick(node.id)} style={{ cursor: "pointer" }}>
                      <ellipse
                        cx={p.x} cy={p.y}
                        rx={58} ry={18}
                        fill={isSelected ? color : "var(--surface, #fff)"}
                        stroke={color}
                        strokeWidth={isSelected ? 2.5 : 1.5}
                        filter={isSelected ? "drop-shadow(0 2px 6px rgba(0,0,0,0.18))" : undefined}
                      />
                      <text
                        x={p.x} y={p.y + 1}
                        textAnchor="middle"
                        dominantBaseline="middle"
                        fontSize={10}
                        fill={isSelected ? "#fff" : "var(--text, #111)"}
                        style={{ userSelect: "none", pointerEvents: "none" }}
                      >
                        {label}
                      </text>
                      <circle cx={p.x - 46} cy={p.y} r={4} fill={color} />
                    </g>
                  );
                })}
              </svg>
            )}
          </div>

          {/* Right panel */}
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>

            {/* Selected objective detail */}
            {selected ? (
              <div className="card" style={{ padding: "var(--space-3)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "var(--space-2)" }}>
                  <h3 style={{ margin: 0, fontSize: "0.875rem", fontWeight: 600 }}>Selected</h3>
                  <button className="btn" onClick={() => setSelected(null)} style={{ padding: "2px 8px", fontSize: "0.75rem" }}>✕</button>
                </div>
                <p style={{ fontSize: "0.875rem", fontWeight: 500, margin: "0 0 var(--space-1)" }}>{selected.title}</p>
                <div style={{ display: "flex", gap: "var(--space-1)", flexWrap: "wrap", marginBottom: "var(--space-2)" }}>
                  <span style={{ fontSize: "0.7rem", background: HEALTH_COLOR[selected.health_current] ?? "#888", color: "#fff", borderRadius: "var(--radius-s)", padding: "1px 6px" }}>
                    {selected.health_current}
                  </span>
                  <span style={{ fontSize: "0.7rem", background: selected.objective_type === "committed" ? "var(--accent)" : "#7c3aed", color: "#fff", borderRadius: "var(--radius-s)", padding: "1px 6px" }}>
                    {selected.objective_type}
                  </span>
                </div>
                <div style={{ fontSize: "0.8rem", color: "var(--text-muted, #888)", marginBottom: "var(--space-1)" }}>
                  Confidence: <strong>{Math.round(selected.confidence_current * 100)}%</strong>
                </div>
                {selected.parent_objective_id && (
                  <div style={{ fontSize: "0.8rem", color: "var(--text-muted, #888)", marginBottom: "var(--space-1)" }}>
                    Parent: <a href={`/okrs/${selected.parent_objective_id}`} style={{ color: "var(--accent)" }}>view</a>
                  </div>
                )}
                <a href={`/okrs/${selected.objective_id}`} className="btn" style={{ display: "block", textAlign: "center", marginTop: "var(--space-2)", fontSize: "0.8rem" }}>
                  Open Detail →
                </a>
              </div>
            ) : (
              <div className="card" style={{ padding: "var(--space-3)", color: "var(--text-muted, #888)", fontSize: "0.8rem", textAlign: "center" }}>
                Click a node to see objective details
              </div>
            )}

            {/* Issues panel */}
            {(orphans.length > 0 || overloaded.length > 0 || missing.length > 0) && (
              <div className="card" style={{ padding: "var(--space-3)" }}>
                <h3 style={{ margin: "0 0 var(--space-2)", fontSize: "0.875rem", fontWeight: 600 }}>Alignment Issues</h3>
                {orphans.length > 0 && (
                  <div style={{ marginBottom: "var(--space-2)" }}>
                    <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "#ca8a04", marginBottom: 4 }}>⚠ Orphaned ({orphans.length})</div>
                    {orphans.slice(0, 3).map((id, i) => (
                      <div key={i} style={{ fontSize: "0.75rem", color: "var(--text-muted, #888)", padding: "1px 0" }}>
                        <a href={`/okrs/${id}`} style={{ color: "var(--accent)" }}>{id.slice(0, 12)}…</a>
                      </div>
                    ))}
                  </div>
                )}
                {missing.length > 0 && (
                  <div style={{ marginBottom: "var(--space-2)" }}>
                    <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "#dc2626", marginBottom: 4 }}>✗ Missing links ({missing.length})</div>
                    <p style={{ fontSize: "0.75rem", color: "var(--text-muted, #888)", margin: 0 }}>These objectives have no parent alignment.</p>
                  </div>
                )}
                {overloaded.length > 0 && (
                  <div>
                    <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "#dc2626", marginBottom: 4 }}>✗ Overloaded teams</div>
                    {overloaded.map((t, i) => <div key={i} style={{ fontSize: "0.75rem", color: "var(--text-muted, #888)" }}>{t}</div>)}
                  </div>
                )}
              </div>
            )}

            {/* Stats */}
            <div className="card" style={{ padding: "var(--space-3)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", padding: "var(--space-1) 0" }}>
                <span>Total objectives</span>
                <strong>{graph?.nodes.length ?? 0}</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", padding: "var(--space-1) 0" }}>
                <span>Connections</span>
                <strong>{filteredEdges.length}</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", padding: "var(--space-1) 0" }}>
                <span>Orphans</span>
                <strong style={{ color: orphans.length > 0 ? "#dc2626" : "inherit" }}>{orphans.length}</strong>
              </div>
            </div>
          </div>
        </div>
      )}
    </PageShell>
  );
}
