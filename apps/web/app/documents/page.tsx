"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { PageShell } from "@/components/page-shell";

const BACKEND = process.env.NEXT_PUBLIC_FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000";

type DocumentItem = {
  file_id: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  created_at: string;
  metadata: {
    format: string;
    document_type: string;
    workspace_id?: string;
  };
};

type WorkspaceItem = { workspace_id: string; name: string; icon: string; color: string };

type FormatFilter = "all" | "docx" | "pptx" | "xlsx" | "pdf";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatIcon(format: string): string {
  switch (format.toLowerCase()) {
    case "docx": return "📝";
    case "pptx": return "📊";
    case "xlsx": return "📊";
    case "pdf":  return "📄";
    default:     return "📎";
  }
}

function SkeletonCard() {
  return (
    <li className="docs-card docs-card-skeleton" aria-hidden="true">
      <div className="docs-card-icon-skeleton" />
      <div className="docs-card-body">
        <div className="docs-skeleton-line docs-skeleton-line-wide" />
        <div className="docs-skeleton-line docs-skeleton-line-narrow" />
      </div>
    </li>
  );
}

export default function DocumentsPage() {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [formatFilter, setFormatFilter] = useState<FormatFilter>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [workspaces, setWorkspaces] = useState<WorkspaceItem[]>([]);
  const [workspaceFilter, setWorkspaceFilter] = useState<string>("all");
  const [previewDoc, setPreviewDoc] = useState<DocumentItem | null>(null);

  useEffect(() => {
    fetch(`${BACKEND}/documents`)
      .then((r) => r.json())
      .then((data: unknown) => {
        setDocs(Array.isArray(data) ? (data as DocumentItem[]) : []);
      })
      .catch(() => setDocs([]))
      .finally(() => setLoading(false));

    fetch(`${BACKEND}/workspaces?org_id=default`)
      .then((r) => r.ok ? r.json() : [])
      .then((data: WorkspaceItem[]) => setWorkspaces(Array.isArray(data) ? data : []))
      .catch(() => {});
  }, []);

  const filtered = useMemo(() => {
    let result = docs;

    // Format filter
    if (formatFilter !== "all") {
      result = result.filter((d) => d.metadata?.format?.toLowerCase() === formatFilter);
    }

    // Workspace filter
    if (workspaceFilter !== "all") {
      result = result.filter((d) => d.metadata?.workspace_id === workspaceFilter);
    }

    // Text search
    const q = searchQuery.trim().toLowerCase();
    if (q) {
      result = result.filter((d) => d.filename.toLowerCase().includes(q));
    }

    return result;
  }, [docs, formatFilter, workspaceFilter, searchQuery]);

  const formatTabs: { key: FormatFilter; label: string }[] = [
    { key: "all", label: "All" },
    { key: "docx", label: "Word" },
    { key: "pptx", label: "PowerPoint" },
    { key: "xlsx", label: "Excel" },
    { key: "pdf", label: "PDF" },
  ];

  return (
    <PageShell
      title="Documents"
      subtitle="Generated reports, memos, and deliverables"
      headerActions={
        <Link href="/" className="docs-chat-link">
          + Ask Friday to create one
        </Link>
      }
    >
    <div className="docs-page">
      {/* Search + workspace filter bar */}
      <div style={{ display: "flex", gap: "0.75rem", marginBottom: "1rem", alignItems: "center", flexWrap: "wrap" }}>
        <input
          type="search"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search documents…"
          style={{
            flex: "1 1 200px",
            padding: "0.5rem 0.75rem",
            border: "1px solid var(--line)",
            borderRadius: 8,
            fontSize: "0.875rem",
            fontFamily: "inherit",
            background: "var(--surface-2)",
            color: "var(--text)",
            minWidth: 180,
          }}
        />
        {workspaces.length > 0 && (
          <select
            value={workspaceFilter}
            onChange={(e) => setWorkspaceFilter(e.target.value)}
            style={{
              padding: "0.5rem 0.75rem",
              border: "1px solid var(--line)",
              borderRadius: 8,
              fontSize: "0.875rem",
              fontFamily: "inherit",
              background: "var(--surface-2)",
              color: "var(--text)",
              flexShrink: 0,
            }}
          >
            <option value="all">All workspaces</option>
            {workspaces.map((ws) => (
              <option key={ws.workspace_id} value={ws.workspace_id}>
                {ws.icon} {ws.name}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Format filter tabs */}
      <div className="docs-filter" role="group" aria-label="Filter by type">
        {formatTabs.map((tab) => (
          <button
            key={tab.key}
            className={formatFilter === tab.key ? "filter-btn active" : "filter-btn"}
            onClick={() => setFormatFilter(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {loading ? (
        <ul className="docs-grid" aria-label="Loading documents">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </ul>
      ) : filtered.length === 0 ? (
        <div className="docs-empty">
          {searchQuery || workspaceFilter !== "all" || formatFilter !== "all" ? (
            <>
              <p>No documents match your filters.</p>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => { setSearchQuery(""); setWorkspaceFilter("all"); setFormatFilter("all"); }}
              >
                Clear filters
              </button>
            </>
          ) : (
            <>
              <p>No documents yet.</p>
              <p>Ask Friday to write something as a Word doc or presentation.</p>
              <Link href="/">Go to chat →</Link>
            </>
          )}
        </div>
      ) : (
        <ul className="docs-grid" aria-label="Document list">
          {filtered.map((doc) => {
            const format = doc.metadata?.format ?? "file";
            const downloadUrl = `/files/${doc.file_id}`;
            const wsName = doc.metadata?.workspace_id
              ? workspaces.find((w) => w.workspace_id === doc.metadata.workspace_id)?.name
              : null;
            return (
              <li key={doc.file_id} className="docs-card">
                <span className="docs-card-icon" aria-hidden="true">
                  {formatIcon(format)}
                </span>
                <div className="docs-card-body">
                  <span className="docs-card-filename" title={doc.filename}>
                    {doc.filename}
                  </span>
                  <span className="docs-card-badges">
                    <span className={`docs-format-badge docs-format-${format.toLowerCase()}`}>
                      {format.toUpperCase()}
                    </span>
                    {doc.metadata?.document_type && (
                      <span className="docs-type-badge">{doc.metadata.document_type}</span>
                    )}
                    {wsName && (
                      <span className="docs-type-badge" style={{ background: "rgba(99,102,241,0.1)", color: "var(--accent)" }}>
                        {wsName}
                      </span>
                    )}
                  </span>
                  <span className="docs-card-meta">
                    <span>{formatBytes(doc.size_bytes)}</span>
                    <span>{new Date(doc.created_at).toLocaleDateString()}</span>
                  </span>
                </div>
                  {format === "pdf" && (
                  <button
                    className="docs-download-btn"
                    style={{ marginRight: "0.25rem" }}
                    onClick={(e) => { e.stopPropagation(); setPreviewDoc(doc); }}
                    aria-label={`Preview ${doc.filename}`}
                  >
                    Preview
                  </button>
                )}
                <button
                  className="docs-download-btn"
                  onClick={() =>
                    window.open(`${BACKEND}${downloadUrl}`, "_blank", "noopener,noreferrer")
                  }
                  aria-label={`Download ${doc.filename}`}
                >
                  Download
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>

    {/* PDF Preview Drawer */}
    {previewDoc && (
      <div
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(0,0,0,0.55)",
          zIndex: 1000,
          display: "flex",
          alignItems: "stretch",
          justifyContent: "flex-end",
        }}
        onClick={() => setPreviewDoc(null)}
        role="dialog"
        aria-modal="true"
        aria-label={`Preview ${previewDoc.filename}`}
      >
        <div
          style={{
            width: "min(860px, 92vw)",
            background: "var(--surface)",
            display: "flex",
            flexDirection: "column",
            boxShadow: "-4px 0 24px rgba(0,0,0,0.2)",
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Drawer header */}
          <div style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "0.875rem 1.25rem",
            borderBottom: "1px solid var(--line)",
            flexShrink: 0,
          }}>
            <div>
              <div style={{ fontWeight: 600, fontSize: "0.9375rem" }}>{previewDoc.filename}</div>
              <div style={{ fontSize: "0.8125rem", color: "var(--text-muted)", marginTop: "0.125rem" }}>
                {formatBytes(previewDoc.size_bytes)} · {new Date(previewDoc.created_at).toLocaleDateString()}
              </div>
            </div>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => window.open(`${BACKEND}/files/${previewDoc.file_id}`, "_blank", "noopener,noreferrer")}
              >
                Download
              </button>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setPreviewDoc(null)}
                aria-label="Close preview"
              >
                ✕
              </button>
            </div>
          </div>
          {/* iframe */}
          <iframe
            src={`${BACKEND}/files/${previewDoc.file_id}`}
            title={previewDoc.filename}
            style={{ flex: 1, border: "none", background: "#fff" }}
          />
        </div>
      </div>
    )}
    </PageShell>
  );
}
