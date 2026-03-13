"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

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
  };
};

type FilterTab = "all" | "docx" | "pptx" | "xlsx" | "pdf";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatIcon(format: string): string {
  switch (format.toLowerCase()) {
    case "docx":
      return "📝";
    case "pptx":
      return "📊";
    case "xlsx":
      return "📊";
    case "pdf":
      return "📄";
    default:
      return "📎";
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
  const [filter, setFilter] = useState<FilterTab>("all");

  useEffect(() => {
    fetch(`${BACKEND}/documents`)
      .then((r) => r.json())
      .then((data: unknown) => {
        setDocs(Array.isArray(data) ? (data as DocumentItem[]) : []);
      })
      .catch(() => setDocs([]))
      .finally(() => setLoading(false));
  }, []);

  const filtered =
    filter === "all"
      ? docs
      : docs.filter((d) => d.metadata?.format?.toLowerCase() === filter);

  const tabs: { key: FilterTab; label: string }[] = [
    { key: "all", label: "All" },
    { key: "docx", label: "Word" },
    { key: "pptx", label: "PowerPoint" },
    { key: "xlsx", label: "Excel" },
    { key: "pdf", label: "PDF" },
  ];

  return (
    <main className="docs-page">
      <header className="docs-header">
        <div>
          <h1>Documents</h1>
          <p className="docs-subtitle">Generated files</p>
        </div>
        <Link href="/" className="docs-chat-link">
          + Ask Friday to create one
        </Link>
      </header>

      <div className="docs-filter" role="group" aria-label="Filter by type">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            className={filter === tab.key ? "filter-btn active" : "filter-btn"}
            onClick={() => setFilter(tab.key)}
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
          <p>No documents yet.</p>
          <p>Ask Friday to write something as a Word doc or presentation.</p>
          <Link href="/">Go to chat →</Link>
        </div>
      ) : (
        <ul className="docs-grid" aria-label="Document list">
          {filtered.map((doc) => {
            const format = doc.metadata?.format ?? "file";
            const downloadUrl = `/files/${doc.file_id}`;
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
                  </span>
                  <span className="docs-card-meta">
                    <span>{formatBytes(doc.size_bytes)}</span>
                    <span>{new Date(doc.created_at).toLocaleDateString()}</span>
                  </span>
                </div>
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
    </main>
  );
}
