"use client";

const BACKEND = process.env.NEXT_PUBLIC_FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000";

export interface DocumentCardProps {
  fileId: string;
  filename: string;
  mimeType: string;
  sizeBytes: number;
  format: string; // "docx" | "pptx" | "xlsx" | "pdf"
  downloadUrl: string; // relative URL like /files/{file_id}
}

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

export function DocumentCard({
  filename,
  sizeBytes,
  format,
  downloadUrl,
}: DocumentCardProps) {
  const handleDownload = () => {
    window.open(`${BACKEND}${downloadUrl}`, "_blank", "noopener,noreferrer");
  };

  return (
    <div className="doc-card">
      <span className="doc-card-icon" aria-hidden="true">
        {formatIcon(format)}
      </span>
      <div className="doc-card-info">
        <span className="doc-card-filename" title={filename}>
          {filename}
        </span>
        <span className="doc-card-meta">
          <span className="doc-card-format">{format.toUpperCase()}</span>
          <span className="doc-card-size">{formatBytes(sizeBytes)}</span>
        </span>
      </div>
      <button
        className="doc-card-download"
        onClick={handleDownload}
        aria-label={`Download ${filename}`}
      >
        Download
      </button>
    </div>
  );
}
