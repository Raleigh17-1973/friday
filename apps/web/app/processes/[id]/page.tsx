"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

const BACKEND = process.env.NEXT_PUBLIC_FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000";

const MermaidDiagram = dynamic(
  () => import("@/components/mermaid-diagram").then((m) => m.MermaidDiagram),
  { ssr: false, loading: () => <div className="mermaid-loading">Rendering diagram…</div> }
);

type ProcessStep = {
  id: string;
  name: string;
  owner: string;
  inputs: string[];
  outputs: string[];
  tools: string[];
  sla: string;
};

type VersionEntry = {
  version: string;
  date: string;
  author: string;
  changes: string;
};

type ProcessDoc = {
  id: string;
  org_id: string;
  process_name: string;
  trigger: string;
  steps: ProcessStep[];
  decision_points: { id: string; condition: string; paths: Record<string, string> }[];
  roles: string[];
  tools: string[];
  exceptions: { trigger: string; handler: string; recovery: string }[];
  kpis: { name: string; target: string }[];
  mermaid_flowchart: string;
  mermaid_swimlane: string;
  completeness_score: number;
  version: string;
  status: string;
  updated_at: string;
  created_at: string;
  changelog: VersionEntry[];
};

type TabId = "overview" | "steps" | "exceptions" | "history";
type DiagramTab = "flowchart" | "swimlane";

export default function ProcessDetailPage() {
  const params = useParams();
  const processId = params?.id as string;

  const [doc, setDoc] = useState<ProcessDoc | null>(null);
  const [history, setHistory] = useState<VersionEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<TabId>("overview");
  const [diagramTab, setDiagramTab] = useState<DiagramTab>("flowchart");
  const [deleteConfirm, setDeleteConfirm] = useState(false);

  useEffect(() => {
    if (!processId) return;
    Promise.all([
      fetch(`${BACKEND}/processes/${processId}`).then((r) => r.json()),
      fetch(`${BACKEND}/processes/${processId}/history`).then((r) => r.json()),
    ])
      .then(([docData, histData]: [unknown, unknown]) => {
        setDoc(docData as ProcessDoc);
        setHistory(Array.isArray(histData) ? (histData as VersionEntry[]) : []);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [processId]);

  if (loading) return <main className="process-detail"><p className="processes-empty">Loading…</p></main>;
  if (!doc) return (
    <main className="process-detail">
      <p className="processes-empty">Process not found. <Link href="/processes">← Back to library</Link></p>
    </main>
  );

  const activeDiagram = diagramTab === "flowchart" ? doc.mermaid_flowchart : doc.mermaid_swimlane;
  const completeness = Math.round(doc.completeness_score * 100);

  return (
    <main className="process-detail">
      {/* ── Header ── */}
      <header className="detail-header">
        <div className="detail-header-left">
          <Link href="/processes" className="back-link">← Process Library</Link>
          <h1>{doc.process_name}</h1>
          <div className="detail-meta">
            <span className={`status-chip status-${doc.status}`}>{doc.status}</span>
            <span className="process-version">v{doc.version}</span>
            <span className="completeness-badge">{completeness}% complete</span>
          </div>
        </div>
        <div className="detail-header-actions">
          <Link href={`/?prefill=Help+me+refine+the+${encodeURIComponent(doc.process_name)}+process`} className="edit-btn">
            ✏ Refine in Chat
          </Link>
        </div>
      </header>

      {/* ── Diagram section ── */}
      <section className="diagram-section" aria-label="Process diagram">
        <div className="diagram-tabs" role="tablist">
          <button
            role="tab"
            aria-selected={diagramTab === "flowchart"}
            className={diagramTab === "flowchart" ? "active" : ""}
            onClick={() => setDiagramTab("flowchart")}
          >
            Flowchart
          </button>
          <button
            role="tab"
            aria-selected={diagramTab === "swimlane"}
            className={diagramTab === "swimlane" ? "active" : ""}
            onClick={() => setDiagramTab("swimlane")}
          >
            Swimlane
          </button>
        </div>
        {activeDiagram ? (
          <MermaidDiagram code={activeDiagram} />
        ) : (
          <p className="mermaid-loading">No diagram available for this view.</p>
        )}
      </section>

      {/* ── Detail tabs ── */}
      <div className="detail-body">
        <nav className="detail-tabs" role="tablist" aria-label="Process details">
          {(["overview", "steps", "exceptions", "history"] as TabId[]).map((t) => (
            <button
              key={t}
              role="tab"
              aria-selected={tab === t}
              className={tab === t ? "active" : ""}
              onClick={() => setTab(t)}
            >
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </nav>

        <div className="detail-panel" role="tabpanel">
          {tab === "overview" && (
            <dl className="overview-grid">
              <dt>Trigger</dt>
              <dd>{doc.trigger || "—"}</dd>

              <dt>Roles</dt>
              <dd>{doc.roles.length > 0 ? doc.roles.join(", ") : "—"}</dd>

              <dt>Tools &amp; Systems</dt>
              <dd>{doc.tools.length > 0 ? doc.tools.join(", ") : "—"}</dd>

              <dt>KPIs / SLAs</dt>
              <dd>
                {doc.kpis.length > 0 ? (
                  <ul className="kpi-list">
                    {doc.kpis.map((k, i) => (
                      <li key={i}><strong>{k.name}:</strong> {k.target}</li>
                    ))}
                  </ul>
                ) : "—"}
              </dd>

              <dt>Decision Points</dt>
              <dd>
                {doc.decision_points.length > 0 ? (
                  <ul className="decision-list">
                    {doc.decision_points.map((d, i) => (
                      <li key={i}>
                        <strong>{d.condition}</strong>
                        {Object.entries(d.paths || {}).map(([k, v]) => (
                          <span key={k} className="decision-path"> {k} → {String(v)}</span>
                        ))}
                      </li>
                    ))}
                  </ul>
                ) : "—"}
              </dd>

              <dt>Last Updated</dt>
              <dd><time dateTime={doc.updated_at}>{new Date(doc.updated_at).toLocaleString()}</time></dd>
            </dl>
          )}

          {tab === "steps" && (
            <ol className="steps-list">
              {doc.steps.map((step, i) => (
                <li key={step.id || i} className="step-item">
                  <div className="step-header">
                    <span className="step-num">{i + 1}</span>
                    <strong>{step.name}</strong>
                    {step.owner && <span className="step-owner">{step.owner}</span>}
                    {step.sla && <span className="step-sla">SLA: {step.sla}</span>}
                  </div>
                  {(step.inputs?.length > 0 || step.outputs?.length > 0) && (
                    <div className="step-io">
                      {step.inputs?.length > 0 && <span>In: {step.inputs.join(", ")}</span>}
                      {step.outputs?.length > 0 && <span>Out: {step.outputs.join(", ")}</span>}
                    </div>
                  )}
                  {step.tools?.length > 0 && (
                    <div className="step-tools">Tools: {step.tools.join(", ")}</div>
                  )}
                </li>
              ))}
              {doc.steps.length === 0 && <p className="processes-empty">No steps captured yet.</p>}
            </ol>
          )}

          {tab === "exceptions" && (
            <ul className="exceptions-list">
              {doc.exceptions.map((ex, i) => (
                <li key={i} className="exception-item">
                  <strong>If:</strong> {ex.trigger}<br />
                  <strong>Handler:</strong> {ex.handler}<br />
                  <strong>Recovery:</strong> {ex.recovery}
                </li>
              ))}
              {doc.exceptions.length === 0 && <p className="processes-empty">No exceptions documented yet.</p>}
            </ul>
          )}

          {tab === "history" && (
            <ol className="history-list" reversed>
              {history.map((entry, i) => (
                <li key={i} className="history-item">
                  <div className="history-header">
                    <span className="process-version">v{entry.version}</span>
                    <span className="history-author">{entry.author}</span>
                    <time dateTime={entry.date}>{new Date(entry.date).toLocaleDateString()}</time>
                  </div>
                  <p>{entry.changes}</p>
                </li>
              ))}
              {history.length === 0 && <p className="processes-empty">No history yet.</p>}
            </ol>
          )}
        </div>
      </div>
    </main>
  );
}
