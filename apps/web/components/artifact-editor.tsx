"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { MarkdownMessage } from "@/components/markdown-message";
import type { Artifact } from "@/components/artifact-card";

const BACKEND = process.env.NEXT_PUBLIC_FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000";
const MAX_VERSIONS = 12;

type Version = { content: string; label: string; savedAt: string };

type EditorMode = "split" | "edit" | "preview";

// ── Minimal markdown toolbar actions ──────────────────────────────────────────

function insertAtCursor(
  el: HTMLTextAreaElement,
  before: string,
  after: string = "",
  placeholder = "text",
): void {
  const { selectionStart: s, selectionEnd: e, value: v } = el;
  const selected = v.slice(s, e) || placeholder;
  const next = v.slice(0, s) + before + selected + after + v.slice(e);
  el.focus();
  el.value = next;
  el.setSelectionRange(s + before.length, s + before.length + selected.length);
  el.dispatchEvent(new Event("input", { bubbles: true }));
}

// ── Export helpers ─────────────────────────────────────────────────────────────

function downloadText(content: string, filename: string, mime = "text/markdown"): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Version History Dropdown ──────────────────────────────────────────────────

function VersionHistoryMenu({
  versions,
  onRevert,
  onClose,
}: {
  versions: Version[];
  onRevert: (v: Version) => void;
  onClose: () => void;
}) {
  if (versions.length === 0) {
    return (
      <div className="ae-dropdown" onMouseLeave={onClose}>
        <div style={{ padding: "0.75rem 1rem", color: "var(--text-muted)", fontSize: "0.8rem" }}>
          No saved versions yet
        </div>
      </div>
    );
  }
  return (
    <div className="ae-dropdown" onMouseLeave={onClose}>
      {versions.map((v, i) => (
        <button key={i} className="ae-dropdown-item" onClick={() => { onRevert(v); onClose(); }}>
          <span style={{ flex: 1, textAlign: "left" }}>{v.label}</span>
          <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>{v.savedAt}</span>
        </button>
      ))}
    </div>
  );
}

// ── Revise Panel ──────────────────────────────────────────────────────────────

function RevisePanel({
  artifact,
  currentContent,
  onClose,
  onContentUpdate,
}: {
  artifact: Artifact;
  currentContent: string;
  onClose: () => void;
  onContentUpdate: (newContent: string) => void;
}) {
  const [instruction, setInstruction] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!instruction.trim()) return;
    setLoading(true);
    setError("");
    try {
      const prompt = `You are revising the following artifact titled "${artifact.name}".
The user wants you to: ${instruction}

Current content:
---
${currentContent}
---

Return ONLY the revised content in markdown format, no preamble or explanation.`;

      const resp = await fetch(`${BACKEND}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: prompt,
          conversation_id: `ae_revise_${Date.now()}`,
          mode: "ACT",
        }),
      });
      const data = await resp.json();
      const revised = data?.response ?? data?.answer ?? data?.text ?? "";
      if (revised) {
        onContentUpdate(revised);
        onClose();
      } else {
        setError("No revised content returned. Try rephrasing your instruction.");
      }
    } catch {
      setError("Failed to reach Friday. Check your connection and try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="ae-revise-panel">
      <div className="ae-revise-header">
        <span style={{ fontWeight: 600, fontSize: "0.875rem" }}>Ask Friday to revise</span>
        <button className="ae-icon-btn" onClick={onClose} aria-label="Close">✕</button>
      </div>
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        <textarea
          className="form-input"
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          placeholder="e.g. Shorten the executive summary, add a risks section, rewrite in a more formal tone…"
          rows={3}
          style={{ fontSize: "0.875rem", resize: "vertical" }}
          autoFocus
        />
        {error && <p style={{ color: "var(--danger)", fontSize: "0.8rem", margin: 0 }}>{error}</p>}
        <div style={{ display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary btn-sm" disabled={loading || !instruction.trim()}>
            {loading ? "Revising…" : "Revise"}
          </button>
        </div>
      </form>
    </div>
  );
}

// ── Main Editor ───────────────────────────────────────────────────────────────

export function ArtifactEditor({
  artifact,
  onClose,
}: {
  artifact: Artifact;
  onClose: () => void;
}) {
  const [content, setContent] = useState(artifact.content);
  const [mode, setMode] = useState<EditorMode>("split");
  const [versions, setVersions] = useState<Version[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [showRevise, setShowRevise] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Save version snapshot
  const saveVersion = useCallback(() => {
    const now = new Date();
    const label = `v${versions.length + 1} — ${now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
    setVersions((prev) => {
      const next = [{ content, label, savedAt: now.toLocaleTimeString() }, ...prev].slice(0, MAX_VERSIONS);
      return next;
    });
    setSavedFlash(true);
    setTimeout(() => setSavedFlash(false), 1200);
  }, [content, versions.length]);

  // Keyboard shortcuts
  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault();
        saveVersion();
      }
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [saveVersion, onClose]);

  function toolbar(action: string) {
    const ta = textareaRef.current;
    if (!ta) return;
    switch (action) {
      case "bold":        return insertAtCursor(ta, "**", "**");
      case "italic":      return insertAtCursor(ta, "_", "_");
      case "h1":          return insertAtCursor(ta, "# ", "", "Heading 1");
      case "h2":          return insertAtCursor(ta, "## ", "", "Heading 2");
      case "h3":          return insertAtCursor(ta, "### ", "", "Heading 3");
      case "ul":          return insertAtCursor(ta, "- ", "", "item");
      case "ol":          return insertAtCursor(ta, "1. ", "", "item");
      case "code":        return insertAtCursor(ta, "`", "`");
      case "codeblock":   return insertAtCursor(ta, "```\n", "\n```", "code");
      case "hr":          return insertAtCursor(ta, "\n---\n", "", "");
      case "blockquote":  return insertAtCursor(ta, "> ", "", "quote");
    }
  }

  const baseName = artifact.name.replace(/\.[^.]+$/, "");

  return (
    <div
      className="ae-overlay"
      role="dialog"
      aria-modal="true"
      aria-label={`Edit: ${artifact.name}`}
    >
      <div className="ae-shell">
        {/* ── Header ─────────────────────────────────────────────────────── */}
        <div className="ae-header">
          <div style={{ display: "flex", alignItems: "center", gap: "0.625rem", minWidth: 0 }}>
            <span style={{ fontSize: "1.1rem" }} aria-hidden>📝</span>
            <span className="ae-title">{artifact.name}</span>
            {savedFlash && (
              <span style={{ fontSize: "0.75rem", color: "var(--success, #16a34a)", animation: "fadeIn 0.2s" }}>
                ✓ Saved
              </span>
            )}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.375rem", flexShrink: 0 }}>
            {/* Mode switcher */}
            <div className="ae-mode-switch" role="group" aria-label="Editor mode">
              {(["edit", "split", "preview"] as EditorMode[]).map((m) => (
                <button
                  key={m}
                  className={mode === m ? "ae-mode-btn active" : "ae-mode-btn"}
                  onClick={() => setMode(m)}
                  title={m.charAt(0).toUpperCase() + m.slice(1)}
                >
                  {m === "edit" ? "Edit" : m === "split" ? "Split" : "Preview"}
                </button>
              ))}
            </div>

            {/* Toolbar buttons (only in edit/split mode) */}
            {mode !== "preview" && (
              <div className="ae-toolbar" role="toolbar" aria-label="Formatting">
                {[
                  { action: "bold", label: "B", title: "Bold (Ctrl+B)" },
                  { action: "italic", label: "I", title: "Italic (Ctrl+I)" },
                ].map(({ action, label, title }) => (
                  <button key={action} className="ae-tb-btn" onClick={() => toolbar(action)} title={title}
                    style={{ fontWeight: action === "bold" ? 700 : 400, fontStyle: action === "italic" ? "italic" : "normal" }}>
                    {label}
                  </button>
                ))}
                <div className="ae-tb-sep" />
                {[
                  { action: "h1", label: "H1" },
                  { action: "h2", label: "H2" },
                  { action: "h3", label: "H3" },
                ].map(({ action, label }) => (
                  <button key={action} className="ae-tb-btn" onClick={() => toolbar(action)} title={label}>{label}</button>
                ))}
                <div className="ae-tb-sep" />
                {[
                  { action: "ul", label: "•—", title: "Bullet list" },
                  { action: "ol", label: "1.", title: "Numbered list" },
                  { action: "code", label: "<>", title: "Inline code" },
                  { action: "codeblock", label: "```", title: "Code block" },
                  { action: "blockquote", label: "❝", title: "Blockquote" },
                ].map(({ action, label, title }) => (
                  <button key={action} className="ae-tb-btn" onClick={() => toolbar(action)} title={title}>{label}</button>
                ))}
              </div>
            )}

            <div className="ae-tb-sep" />

            {/* History */}
            <div style={{ position: "relative" }}>
              <button
                className="ae-icon-btn"
                onClick={() => setShowHistory((v) => !v)}
                title="Version history"
              >
                🕐 {versions.length > 0 && <span className="ae-badge">{versions.length}</span>}
              </button>
              {showHistory && (
                <VersionHistoryMenu
                  versions={versions}
                  onRevert={(v) => setContent(v.content)}
                  onClose={() => setShowHistory(false)}
                />
              )}
            </div>

            {/* Save version */}
            <button className="ae-icon-btn" onClick={saveVersion} title="Save version (⌘S)">
              💾
            </button>

            {/* Ask Friday to revise */}
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => setShowRevise((v) => !v)}
              style={{ fontSize: "0.78rem" }}
            >
              ✨ Revise
            </button>

            {/* Export */}
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => downloadText(content, `${baseName}.md`)}
              title="Export as Markdown"
              style={{ fontSize: "0.78rem" }}
            >
              ↓ .md
            </button>

            {/* Close */}
            <button className="ae-icon-btn" onClick={onClose} aria-label="Close editor">✕</button>
          </div>
        </div>

        {/* ── Revise Panel ────────────────────────────────────────────────── */}
        {showRevise && (
          <RevisePanel
            artifact={artifact}
            currentContent={content}
            onClose={() => setShowRevise(false)}
            onContentUpdate={(newContent) => {
              saveVersion(); // save current before replacing
              setContent(newContent);
            }}
          />
        )}

        {/* ── Editor Body ─────────────────────────────────────────────────── */}
        <div className="ae-body" data-mode={mode}>
          {/* Edit pane */}
          {mode !== "preview" && (
            <div className="ae-pane ae-edit-pane">
              <div className="ae-pane-label">Markdown</div>
              <textarea
                ref={textareaRef}
                className="ae-textarea"
                value={content}
                onChange={(e) => setContent(e.target.value)}
                spellCheck
                autoFocus={mode === "edit"}
                placeholder="Start writing in Markdown…"
              />
            </div>
          )}

          {/* Preview pane */}
          {mode !== "edit" && (
            <div className="ae-pane ae-preview-pane">
              <div className="ae-pane-label">Preview</div>
              <div className="ae-preview-scroll">
                {content.trim() ? (
                  <MarkdownMessage content={content} />
                ) : (
                  <p style={{ color: "var(--text-muted)", fontStyle: "italic", fontSize: "0.875rem" }}>
                    Nothing to preview yet.
                  </p>
                )}
              </div>
            </div>
          )}
        </div>

        {/* ── Footer ─────────────────────────────────────────────────────── */}
        <div className="ae-footer">
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
            {content.split(/\s+/).filter(Boolean).length} words · {content.length} chars
          </span>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button className="btn btn-ghost btn-sm" onClick={onClose}>Close without saving</button>
            <button className="btn btn-primary btn-sm" onClick={saveVersion}>
              {savedFlash ? "✓ Saved" : "Save version"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
