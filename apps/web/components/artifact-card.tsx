"use client";

import { useState } from "react";
import { MarkdownMessage } from "@/components/markdown-message";
import { ArtifactEditor } from "@/components/artifact-editor";

export type Artifact = {
  artifact_id: string;
  name: string;
  type: "memo" | "report" | "table" | "checklist" | "analysis" | "document" | string;
  content: string;
  created_at: string;
  file_id?: string;
  download_url?: string;
};

const TYPE_ICON: Record<string, string> = {
  memo:      "🗒",
  report:    "📊",
  table:     "📋",
  checklist: "✅",
  analysis:  "🔍",
  document:  "📄",
};

function typeIcon(type: string) {
  return TYPE_ICON[type.toLowerCase()] ?? "📄";
}

function preview(content: string): string {
  // Strip markdown syntax for the 2-line preview
  const stripped = content
    .replace(/```[\s\S]*?```/g, "[code]")
    .replace(/#{1,6}\s*/g, "")
    .replace(/\*\*/g, "")
    .replace(/[*_`]/g, "")
    .replace(/\n+/g, " ")
    .trim();
  return stripped.length > 140 ? `${stripped.slice(0, 140)}…` : stripped;
}

function ArtifactModal({ artifact, onClose }: { artifact: Artifact; onClose: () => void }) {
  return (
    <div
      className="artifact-modal-overlay"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={artifact.name}
    >
      <div
        className="artifact-modal"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="artifact-modal-header">
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <span aria-hidden="true">{typeIcon(artifact.type)}</span>
            <h2 className="artifact-modal-title">{artifact.name}</h2>
          </div>
          <button
            className="artifact-modal-close"
            onClick={onClose}
            aria-label="Close preview"
          >
            ✕
          </button>
        </header>
        <div className="artifact-modal-body">
          <MarkdownMessage content={artifact.content} />
        </div>
        {artifact.download_url && (
          <footer className="artifact-modal-footer">
            <a
              href={artifact.download_url}
              download={artifact.name}
              className="btn btn-primary btn-sm"
              target="_blank"
              rel="noopener noreferrer"
            >
              Download
            </a>
          </footer>
        )}
      </div>
    </div>
  );
}

const TEXT_TYPES = new Set(["memo", "report", "analysis", "checklist", "document", "text", "markdown"]);

export function ArtifactCard({ artifact }: { artifact: Artifact }) {
  const [showPreview, setShowPreview] = useState(false);
  const [showEditor, setShowEditor] = useState(false);
  const isText = TEXT_TYPES.has(artifact.type.toLowerCase());

  return (
    <>
      <div className="artifact-card">
        <div className="artifact-card-top">
          <span className="artifact-card-icon" aria-hidden="true">
            {typeIcon(artifact.type)}
          </span>
          <div className="artifact-card-info">
            <span className="artifact-card-name">{artifact.name}</span>
            <span className="artifact-card-meta">
              {new Date(artifact.created_at).toLocaleDateString()}
            </span>
          </div>
        </div>
        <p className="artifact-card-preview">{preview(artifact.content)}</p>
        <div className="artifact-card-actions">
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => setShowPreview(true)}
          >
            Preview
          </button>
          {isText && (
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => setShowEditor(true)}
              title="Open in editor"
            >
              Edit
            </button>
          )}
          {artifact.download_url && (
            <a
              href={artifact.download_url}
              download={artifact.name}
              className="btn btn-ghost btn-sm"
              target="_blank"
              rel="noopener noreferrer"
            >
              Download
            </a>
          )}
        </div>
      </div>

      {showPreview && (
        <ArtifactModal artifact={artifact} onClose={() => setShowPreview(false)} />
      )}

      {showEditor && (
        <ArtifactEditor artifact={artifact} onClose={() => setShowEditor(false)} />
      )}
    </>
  );
}
