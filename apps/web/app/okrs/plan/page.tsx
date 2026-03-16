"use client";

import { useEffect, useState } from "react";
import { PageShell } from "@/components/page-shell";

const BACKEND = process.env.NEXT_PUBLIC_FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000";

interface Period { period_id: string; name: string; }
interface OrgNode { node_id: string; name: string; }
interface ValidationIssue { rule_id: string; severity: string; message: string; suggestion: string; }
interface KRDraft { title: string; kr_type: string; baseline_value: string; target_value: string; unit: string; direction: string; description: string; }

export default function OKRPlanPage() {
  const [step, setStep] = useState(1);
  const [periods, setPeriods] = useState<Period[]>([]);
  const [nodes, setNodes] = useState<OrgNode[]>([]);
  const [periodId, setPeriodId] = useState("");
  const [nodeId, setNodeId] = useState("");
  const [objTitle, setObjTitle] = useState("");
  const [objType, setObjType] = useState("committed");
  const [objRationale, setObjRationale] = useState("");
  const [krs, setKrs] = useState<KRDraft[]>([{ title: "", kr_type: "metric", baseline_value: "", target_value: "", unit: "", direction: "increase", description: "" }]);
  const [issues, setIssues] = useState<ValidationIssue[]>([]);
  const [publishing, setPublishing] = useState(false);
  const [published, setPublished] = useState<{objective_id: string; title: string} | null>(null);

  // AI Assist state
  const [aiLoading, setAiLoading] = useState(false);
  const [aiResponse, setAiResponse] = useState("");
  const [aiSuggestion, setAiSuggestion] = useState("");

  useEffect(() => {
    Promise.all([
      fetch(`${BACKEND}/okrs/periods?org_id=org-1`).then(r => r.json()),
      fetch(`${BACKEND}/okrs/org-nodes?org_id=org-1`).then(r => r.json()),
    ]).then(([pd, nd]) => {
      setPeriods(pd.periods ?? []);
      setNodes(nd.org_nodes ?? []);
    }).catch(() => undefined);
  }, []);

  function addKR() {
    setKrs(k => [...k, { title: "", kr_type: "metric", baseline_value: "", target_value: "", unit: "", direction: "increase", description: "" }]);
  }
  function removeKR(i: number) {
    setKrs(k => k.filter((_, idx) => idx !== i));
  }
  function updateKR(i: number, field: keyof KRDraft, value: string) {
    setKrs(k => k.map((kr, idx) => idx === i ? { ...kr, [field]: value } : kr));
  }

  async function requestAIFeedback() {
    if (!objTitle.trim()) return;
    setAiLoading(true);
    setAiResponse("");
    setAiSuggestion("");
    try {
      const typeLabel = objType === "committed"
        ? "Committed (score 1.0 is expected — misses are problems)"
        : "Aspirational (~0.7 is strong — stretch without shame)";
      const prompt = [
        "You are an OKR Writing Coach. Analyze this objective draft and provide concise, actionable feedback.",
        "",
        `Title: "${objTitle}"`,
        `Type: ${typeLabel}`,
        `Rationale: "${objRationale.trim() || "none provided"}"`,
        "",
        "Please provide:",
        "1. A quality score (1–10) with one sentence of reasoning",
        "2. A rewritten title that starts with an outcome verb (Grow, Achieve, Reduce, Launch, Deliver, Eliminate, etc.) and is measurable or clearly directional",
        "3. One or two specific improvements or clarifying questions that would make this objective stronger",
        "",
        "Format your rewritten title on its own line starting exactly with: Rewrite: ",
      ].join("\n");

      const res = await fetch(`${BACKEND}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: prompt,
          conversation_id: `okr-assist-${Date.now()}`,
          mode: "ask",
        }),
      });
      const data = await res.json();
      const text: string = data.response ?? data.answer ?? data.text ?? data.message ?? JSON.stringify(data);
      setAiResponse(text);

      // Extract suggested rewrite line
      const match = text.match(/Rewrite:\s*["""']?([^\n"""']+)["""']?/i);
      if (match) setAiSuggestion(match[1].trim().replace(/^["']|["']$/g, ""));
    } catch {
      setAiResponse("Unable to reach Friday. Make sure the API server is running on port 8000.");
    }
    setAiLoading(false);
  }

  async function publish() {
    setPublishing(true);
    try {
      const objRes = await fetch(`${BACKEND}/okrs/objectives`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ period_id: periodId, org_node_id: nodeId, title: objTitle, objective_type: objType, rationale: objRationale, org_id: "org-1", owner_user_id: "user-1" }),
      });
      const objData = await objRes.json();
      if (!objRes.ok) { setIssues(objData.validation_issues ?? []); setPublishing(false); return; }
      setIssues(objData.validation_issues ?? []);
      const objId = objData.objective?.objective_id;
      if (!objId) { setPublishing(false); return; }
      for (const kr of krs.filter(k => k.title.trim())) {
        await fetch(`${BACKEND}/okrs/objectives/${objId}/key-results`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: kr.title, kr_type: kr.kr_type, baseline_value: kr.baseline_value ? parseFloat(kr.baseline_value) : null, target_value: kr.target_value ? parseFloat(kr.target_value) : null, unit: kr.unit, direction: kr.direction, description: kr.description, owner_user_id: "user-1", org_id: "org-1" }),
        }).catch(() => undefined);
      }
      setPublished({ objective_id: objId, title: objTitle });
    } catch { /* ignore */ }
    setPublishing(false);
  }

  const STEPS = ["Choose Period & Team", "Draft Objective", "Add Key Results", "Review & Publish"];
  const errorIssues = issues.filter(i => i.severity === "error");
  const warnIssues = issues.filter(i => i.severity === "warning");

  if (published) {
    return (
      <PageShell title="OKR Planning Workspace" breadcrumbs={[{ label: "OKRs", href: "/okrs" }, { label: "Plan" }]}>
        <div className="card" style={{ padding: "var(--space-4)", textAlign: "center", maxWidth: 480, margin: "0 auto" }}>
          <div style={{ fontSize: "2rem", marginBottom: "var(--space-2)" }}>✅</div>
          <h2 style={{ marginBottom: "var(--space-2)" }}>Objective Published</h2>
          <p style={{ color: "var(--text-muted, #888)", marginBottom: "var(--space-3)" }}>"{published.title}" has been created with {krs.filter(k => k.title.trim()).length} key result(s).</p>
          <div style={{ display: "flex", gap: "var(--space-2)", justifyContent: "center" }}>
            <a href={`/okrs/${published.objective_id}`} className="btn btn-primary">View Objective</a>
            <a href="/okrs" className="btn">Back to OKRs</a>
          </div>
        </div>
      </PageShell>
    );
  }

  return (
    <PageShell title="OKR Planning Workspace" subtitle="Step-by-step OKR creation with real-time validation" breadcrumbs={[{ label: "OKRs", href: "/okrs" }, { label: "Plan" }]}>
      {/* Step indicator */}
      <div style={{ display: "flex", gap: 0, marginBottom: "var(--space-4)", alignItems: "center" }}>
        {STEPS.map((s, i) => (
          <div key={s} style={{ display: "flex", alignItems: "center", flex: 1 }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", cursor: i < step - 1 ? "pointer" : "default" }} onClick={() => { if (i < step - 1) setStep(i + 1); }}>
              <div style={{ width: 28, height: 28, borderRadius: "50%", background: step > i + 1 ? "#22c55e" : step === i + 1 ? "var(--accent)" : "var(--border)", color: step >= i + 1 ? "#fff" : "var(--text-muted, #888)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.8rem", fontWeight: 700, transition: "background 0.2s" }}>
                {step > i + 1 ? "✓" : i + 1}
              </div>
              <div style={{ fontSize: "0.7rem", color: step === i + 1 ? "var(--accent)" : "var(--text-muted, #888)", marginTop: 4, textAlign: "center", maxWidth: 80 }}>{s}</div>
            </div>
            {i < STEPS.length - 1 && <div style={{ flex: 1, height: 1, background: step > i + 1 ? "#22c55e" : "var(--border)", margin: "0 8px", marginBottom: 20 }} />}
          </div>
        ))}
      </div>

      <div className="card" style={{ padding: "var(--space-4)", maxWidth: 600, margin: "0 auto" }}>

        {/* ── Step 1 ── */}
        {step === 1 && (
          <div>
            <h3 style={{ marginBottom: "var(--space-3)" }}>Choose Period &amp; Team</h3>
            {periods.length === 0 && nodes.length === 0 && (
              <div style={{ background: "#fef3c7", border: "1px solid #fcd34d", borderRadius: "var(--radius-s)", padding: "var(--space-2) var(--space-3)", marginBottom: "var(--space-3)", fontSize: "0.875rem", color: "#92400e" }}>
                <strong>Setup required</strong> — No periods or teams exist yet.{" "}
                <a href="/okrs/setup" style={{ color: "#92400e", fontWeight: 600, textDecoration: "underline" }}>Go to OKR Setup →</a>
              </div>
            )}
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
                  <label style={{ fontSize: "0.875rem", fontWeight: 500 }}>OKR Period *</label>
                  <a href="/okrs/setup?tab=periods" style={{ fontSize: "0.75rem", color: "var(--accent)", textDecoration: "none" }}>+ Create period</a>
                </div>
                <select className="form-input" style={{ width: "100%" }} value={periodId} onChange={e => setPeriodId(e.target.value)}>
                  <option value="">Select a period</option>
                  {periods.map(p => <option key={p.period_id} value={p.period_id}>{p.name}</option>)}
                </select>
                {periods.length === 0 && <p style={{ margin: "4px 0 0", fontSize: "0.75rem", color: "var(--text-muted,#888)" }}>No periods configured — <a href="/okrs/setup" style={{ color: "var(--accent)" }}>create one in Setup</a></p>}
              </div>
              <div>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
                  <label style={{ fontSize: "0.875rem", fontWeight: 500 }}>Team / Org Node *</label>
                  <a href="/okrs/setup?tab=teams" style={{ fontSize: "0.75rem", color: "var(--accent)", textDecoration: "none" }}>+ Add team</a>
                </div>
                <select className="form-input" style={{ width: "100%" }} value={nodeId} onChange={e => setNodeId(e.target.value)}>
                  <option value="">Select a team</option>
                  {nodes.map(n => <option key={n.node_id} value={n.node_id}>{n.name}</option>)}
                </select>
                {nodes.length === 0 && <p style={{ margin: "4px 0 0", fontSize: "0.75rem", color: "var(--text-muted,#888)" }}>No teams configured — <a href="/okrs/setup" style={{ color: "var(--accent)" }}>create one in Setup</a></p>}
              </div>
              <button className="btn btn-primary" disabled={!periodId || !nodeId} onClick={() => setStep(2)} style={{ alignSelf: "flex-end" }}>Next →</button>
            </div>
          </div>
        )}

        {/* ── Step 2 ── */}
        {step === 2 && (
          <div>
            <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: "var(--space-3)" }}>
              <h3>Draft Objective</h3>
              <span style={{ fontSize: "0.75rem", color: "var(--text-muted,#888)" }}>AI coach available below</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
              <div>
                <label style={{ display: "block", marginBottom: 4, fontSize: "0.875rem", fontWeight: 500 }}>Title *</label>
                <input
                  className="form-input"
                  style={{ width: "100%" }}
                  type="text"
                  placeholder="Become the undisputed market leader in SMB HR"
                  value={objTitle}
                  onChange={e => { setObjTitle(e.target.value); setAiResponse(""); setAiSuggestion(""); }}
                />
                <p style={{ fontSize: "0.75rem", color: "var(--text-muted, #888)", marginTop: 4 }}>Use an outcome verb: Grow, Achieve, Reduce, Launch, Deliver…</p>
              </div>
              <div>
                <label style={{ display: "block", marginBottom: 4, fontSize: "0.875rem", fontWeight: 500 }}>Type</label>
                <select className="form-input" style={{ width: "100%" }} value={objType} onChange={e => setObjType(e.target.value)}>
                  <option value="committed">Committed — 1.0 is expected. Misses are problems.</option>
                  <option value="aspirational">Aspirational — 0.7 is strong. Stretch without shame.</option>
                </select>
              </div>
              <div>
                <label style={{ display: "block", marginBottom: 4, fontSize: "0.875rem", fontWeight: 500 }}>Rationale</label>
                <textarea
                  className="form-input"
                  style={{ width: "100%", minHeight: 80 }}
                  placeholder="Why does this matter now? What's the strategic context?"
                  value={objRationale}
                  onChange={e => setObjRationale(e.target.value)}
                />
              </div>

              {/* ── AI Feedback panel ── */}
              <div style={{ borderTop: "1px solid var(--border)", paddingTop: "var(--space-2)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                  <button
                    type="button"
                    className="btn"
                    style={{ fontSize: "0.8rem", display: "flex", alignItems: "center", gap: 5 }}
                    onClick={requestAIFeedback}
                    disabled={!objTitle.trim() || aiLoading}
                  >
                    {aiLoading
                      ? <><span style={{ display: "inline-block", width: 12, height: 12, border: "2px solid var(--border)", borderTopColor: "var(--accent)", borderRadius: "50%", animation: "spin 0.7s linear infinite" }} /> Analyzing…</>
                      : <>✨ AI Feedback</>
                    }
                  </button>
                  {!objTitle.trim() && (
                    <span style={{ fontSize: "0.72rem", color: "var(--text-muted,#888)" }}>Enter a title first</span>
                  )}
                  {aiResponse && !aiLoading && (
                    <button
                      type="button"
                      className="btn"
                      style={{ fontSize: "0.72rem", marginLeft: "auto", color: "var(--text-muted,#888)" }}
                      onClick={() => { setAiResponse(""); setAiSuggestion(""); }}
                    >
                      Clear
                    </button>
                  )}
                </div>

                {aiResponse && (
                  <div style={{
                    marginTop: "var(--space-2)",
                    padding: "var(--space-2) var(--space-3)",
                    background: "rgba(99,102,241,0.05)",
                    border: "1px solid rgba(99,102,241,0.18)",
                    borderRadius: "var(--radius-m)",
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: "var(--space-1)" }}>
                      <span style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--accent)", letterSpacing: "0.04em", textTransform: "uppercase" }}>✨ OKR Writing Coach</span>
                    </div>
                    <div style={{ fontSize: "0.8rem", whiteSpace: "pre-wrap", lineHeight: 1.65, color: "var(--text, #111)" }}>
                      {aiResponse}
                    </div>

                    {aiSuggestion && (
                      <div style={{ marginTop: "var(--space-2)", paddingTop: "var(--space-2)", borderTop: "1px solid rgba(99,102,241,0.12)" }}>
                        <label style={{ fontSize: "0.72rem", fontWeight: 600, color: "var(--text-muted,#888)", display: "block", marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.04em" }}>
                          Suggested rewrite — edit then apply
                        </label>
                        <div style={{ display: "flex", gap: "var(--space-1)" }}>
                          <input
                            className="form-input"
                            style={{ flex: 1, fontSize: "0.82rem" }}
                            value={aiSuggestion}
                            onChange={e => setAiSuggestion(e.target.value)}
                          />
                          <button
                            type="button"
                            className="btn btn-primary"
                            style={{ fontSize: "0.78rem", whiteSpace: "nowrap" }}
                            onClick={() => {
                              setObjTitle(aiSuggestion);
                              setAiResponse("");
                              setAiSuggestion("");
                            }}
                          >
                            Apply
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
              {/* ── end AI panel ── */}

              <div style={{ display: "flex", gap: "var(--space-2)", justifyContent: "flex-end", marginTop: "var(--space-1)" }}>
                <button className="btn" onClick={() => setStep(1)}>← Back</button>
                <button className="btn btn-primary" disabled={!objTitle.trim()} onClick={() => setStep(3)}>Next →</button>
              </div>
            </div>
          </div>
        )}

        {/* ── Step 3 ── */}
        {step === 3 && (
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
              <h3>Add Key Results</h3>
              <button className="btn" onClick={addKR} style={{ fontSize: "0.8rem" }}>+ Add KR</button>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
              {krs.map((kr, i) => (
                <div key={i} style={{ padding: "var(--space-2)", border: "1px solid var(--border)", borderRadius: "var(--radius-m)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "var(--space-1)" }}>
                    <span style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-muted, #888)" }}>KR {i + 1}</span>
                    {krs.length > 1 && <button className="btn" style={{ fontSize: "0.7rem", padding: "2px 8px" }} onClick={() => removeKR(i)}>Remove</button>}
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
                    <input className="form-input" style={{ width: "100%" }} type="text" placeholder="Grow NPS from 42 to 65" value={kr.title} onChange={e => updateKR(i, "title", e.target.value)} />
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: "var(--space-1)" }}>
                      <select className="form-input" value={kr.kr_type} onChange={e => updateKR(i, "kr_type", e.target.value)}>
                        <option value="metric">Metric</option>
                        <option value="milestone">Milestone</option>
                        <option value="binary">Binary</option>
                      </select>
                      {kr.kr_type === "metric" && <>
                        <input className="form-input" type="number" placeholder="Baseline" value={kr.baseline_value} onChange={e => updateKR(i, "baseline_value", e.target.value)} />
                        <input className="form-input" type="number" placeholder="Target" value={kr.target_value} onChange={e => updateKR(i, "target_value", e.target.value)} />
                        <input className="form-input" type="text" placeholder="Unit" value={kr.unit} onChange={e => updateKR(i, "unit", e.target.value)} />
                      </>}
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <div style={{ display: "flex", gap: "var(--space-2)", justifyContent: "flex-end", marginTop: "var(--space-3)" }}>
              <button className="btn" onClick={() => setStep(2)}>← Back</button>
              <button className="btn btn-primary" onClick={() => setStep(4)}>Review →</button>
            </div>
          </div>
        )}

        {/* ── Step 4 ── */}
        {step === 4 && (
          <div>
            <h3 style={{ marginBottom: "var(--space-3)" }}>Review & Publish</h3>
            <div style={{ padding: "var(--space-2)", background: "var(--surface)", borderRadius: "var(--radius-m)", marginBottom: "var(--space-3)" }}>
              <div style={{ display: "flex", gap: "var(--space-1)", alignItems: "center", marginBottom: "var(--space-1)" }}>
                <span style={{ background: objType === "committed" ? "var(--accent)" : "#7c3aed", color: "#fff", borderRadius: "var(--radius-s)", padding: "1px 6px", fontSize: "0.7rem" }}>{objType}</span>
                <strong>{objTitle}</strong>
              </div>
              {objRationale && <p style={{ fontSize: "0.8rem", color: "var(--text-muted, #888)", marginBottom: "var(--space-1)" }}>{objRationale}</p>}
              <div style={{ marginTop: "var(--space-2)" }}>
                {krs.filter(k => k.title.trim()).map((kr, i) => (
                  <div key={i} style={{ fontSize: "0.8rem", display: "flex", gap: "var(--space-1)", alignItems: "center", padding: "4px 0", borderTop: "1px solid var(--border)" }}>
                    <span style={{ background: "#0891b2", color: "#fff", borderRadius: "var(--radius-s)", padding: "1px 5px", fontSize: "0.65rem" }}>{kr.kr_type}</span>
                    <span>{kr.title}</span>
                    {kr.baseline_value && <span style={{ color: "var(--text-muted, #888)" }}>{kr.baseline_value} → {kr.target_value} {kr.unit}</span>}
                  </div>
                ))}
              </div>
            </div>

            {errorIssues.length > 0 && (
              <div style={{ padding: "var(--space-2)", background: "rgba(239,68,68,0.08)", borderRadius: "var(--radius-s)", marginBottom: "var(--space-2)", border: "1px solid rgba(239,68,68,0.3)" }}>
                <div style={{ fontWeight: 600, fontSize: "0.8rem", color: "#ef4444", marginBottom: 4 }}>⚠ Validation errors (will still publish)</div>
                {errorIssues.map(i => <div key={i.rule_id} style={{ fontSize: "0.75rem", color: "#ef4444" }}>[{i.rule_id}] {i.message}</div>)}
              </div>
            )}
            {warnIssues.length > 0 && (
              <div style={{ padding: "var(--space-2)", background: "rgba(234,179,8,0.08)", borderRadius: "var(--radius-s)", marginBottom: "var(--space-2)", border: "1px solid rgba(234,179,8,0.3)" }}>
                {warnIssues.map(i => <div key={i.rule_id} style={{ fontSize: "0.75rem", color: "#eab308" }}>ℹ [{i.rule_id}] {i.message}</div>)}
              </div>
            )}

            <div style={{ display: "flex", gap: "var(--space-2)", justifyContent: "flex-end" }}>
              <button className="btn" onClick={() => setStep(3)}>← Back</button>
              <button className="btn btn-primary" disabled={publishing} onClick={publish}>{publishing ? "Publishing…" : "Publish OKRs"}</button>
            </div>
          </div>
        )}
      </div>

      {/* Spinner keyframe — injected inline once */}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </PageShell>
  );
}
