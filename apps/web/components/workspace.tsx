"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  BarChart2,
  FileText,
  Folders,
  Settings,
  Target,
  Workflow,
  type LucideIcon,
} from "lucide-react";

const BACKEND = process.env.NEXT_PUBLIC_FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000";

import { useChatState } from "@/components/use-chat-state";
import { MarkdownMessage } from "@/components/markdown-message";
import type { ChatMode, ConversationThread, FridayMessage } from "@/lib/types";

// Mermaid is browser-only (DOM required) — load dynamically, no SSR
const MermaidDiagram = dynamic(
  () => import("@/components/mermaid-diagram").then((m) => m.MermaidDiagram),
  { ssr: false, loading: () => <div className="mermaid-loading">Rendering diagram…</div> }
);

// DocumentCard — lazy-loaded so it doesn't bloat the initial bundle
const DocumentCard = dynamic(
  () => import("@/components/document-card").then((m) => m.DocumentCard),
  { ssr: false }
);

// ── Mermaid fence parser ───────────────────────────────────────────────────
// Splits a message string into alternating text / mermaid segments.
type TextSegment   = { kind: "text"; content: string };
type DiagramSegment = { kind: "diagram"; code: string };
type Segment = TextSegment | DiagramSegment;

const MERMAID_FENCE_RE = /```mermaid\n([\s\S]*?)```/g;

function parseSegments(text: string): Segment[] {
  const segments: Segment[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  MERMAID_FENCE_RE.lastIndex = 0;

  while ((match = MERMAID_FENCE_RE.exec(text)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ kind: "text", content: text.slice(lastIndex, match.index) });
    }
    segments.push({ kind: "diagram", code: match[1] });
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    segments.push({ kind: "text", content: text.slice(lastIndex) });
  }

  return segments.length > 0 ? segments : [{ kind: "text", content: text }];
}

// ── Nav items ──────────────────────────────────────────────────────────────
type NavItem = { label: string; href: string; icon: LucideIcon };

const NAV_ITEMS: NavItem[] = [
  { label: "Process Library", href: "/processes",  icon: Workflow  },
  { label: "Documents",       href: "/documents",  icon: FileText  },
  { label: "Analytics",       href: "/analytics",  icon: BarChart2 },
  { label: "OKRs",            href: "/okrs",       icon: Target    },
  { label: "Workspaces",      href: "/workspaces", icon: Folders   },
  { label: "Settings",        href: "/settings",   icon: Settings  },
];

// ── Status dot ────────────────────────────────────────────────────────────
function StatusDot({ state }: { state: string }) {
  const isConnected  = state === "connected";
  const isDegraded   = state === "connecting" || state === "reconnecting";
  const dotClass     = isConnected ? "status-dot-green"
                     : isDegraded  ? "status-dot-amber"
                     : "status-dot-red";

  return (
    <span className="status-dot-wrap" title={`Connection: ${state}`}>
      <span className={`status-dot ${dotClass}`} />
      {!isConnected && (
        <span className="status-dot-label">
          {isDegraded ? "Connecting…" : "Connection issues"}
        </span>
      )}
    </span>
  );
}

// ── Workspace items ───────────────────────────────────────────────────────
type WorkspaceItem = { workspace_id: string; name: string; icon: string; color: string; slug: string };

function LeftRail({
  threads,
  activeThreadId,
  onSelect,
  onCreate,
  onRename,
  onDelete
}: {
  threads: ConversationThread[];
  activeThreadId: string;
  onSelect: (threadId: string) => void;
  onCreate: () => void;
  onRename: (threadId: string) => void;
  onDelete: (threadId: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [workspaces, setWorkspaces] = useState<WorkspaceItem[]>([]);
  // Per-thread context menu state: threadId → "menu" | "confirm-delete" | null
  const [menuOpen, setMenuOpen] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return threads;
    return threads.filter((thread) => thread.title.toLowerCase().includes(q));
  }, [threads, query]);

  useEffect(() => {
    fetch(`${BACKEND}/workspaces?org_id=default`)
      .then((r) => r.ok ? r.json() : [])
      .then((data: WorkspaceItem[]) => setWorkspaces(Array.isArray(data) ? data.slice(0, 6) : []))
      .catch(() => {});
  }, []);

  // Close menu when clicking outside
  useEffect(() => {
    if (!menuOpen) return;
    const close = () => setMenuOpen(null);
    document.addEventListener("click", close);
    return () => document.removeEventListener("click", close);
  }, [menuOpen]);

  const handleMenuToggle = (e: React.MouseEvent, threadId: string) => {
    e.stopPropagation();
    setMenuOpen((prev) => prev === threadId ? null : threadId);
    setConfirmDelete(null);
  };

  const handleRename = (e: React.MouseEvent, threadId: string) => {
    e.stopPropagation();
    setMenuOpen(null);
    onRename(threadId);
  };

  const handleDeleteClick = (e: React.MouseEvent, threadId: string) => {
    e.stopPropagation();
    setMenuOpen(null);
    setConfirmDelete(threadId);
  };

  const handleDeleteConfirm = (threadId: string) => {
    setConfirmDelete(null);
    onDelete(threadId);
  };

  const currentPath = typeof window !== "undefined" ? window.location.pathname : "";

  return (
    <aside className="left-rail" aria-label="Threads and saved context">
      <header className="rail-header">Friday</header>

      <nav className="rail-nav" aria-label="Main navigation">
        {NAV_ITEMS.map(({ label, href, icon: Icon }) => (
          <a
            key={href}
            href={href}
            className={`rail-nav-link${currentPath.startsWith(href) ? " rail-nav-link-active" : ""}`}
          >
            <Icon size={16} strokeWidth={1.75} aria-hidden="true" />
            {label}
          </a>
        ))}
      </nav>

      <button className="new-chat" onClick={onCreate}>
        + New chat
      </button>
      <input
        className="search"
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Search threads"
        aria-label="Search threads"
      />
      <section>
        <h2>Threads</h2>
        <ul className="thread-list">
          {filtered.map((thread) => (
            <li key={thread.id} className={`thread-item${thread.id === activeThreadId ? " active" : ""}`}>
              <button className="thread-title" onClick={() => onSelect(thread.id)}>
                {thread.title}
              </button>

              {/* Context menu trigger — visible on hover via CSS */}
              <button
                className="thread-menu-btn"
                aria-label={`Options for ${thread.title}`}
                onClick={(e) => handleMenuToggle(e, thread.id)}
              >
                ···
              </button>

              {/* Dropdown menu */}
              {menuOpen === thread.id && (
                <div className="thread-menu" role="menu" onClick={(e) => e.stopPropagation()}>
                  <button
                    className="thread-menu-item"
                    role="menuitem"
                    onClick={(e) => handleRename(e, thread.id)}
                  >
                    Rename
                  </button>
                  <button
                    className="thread-menu-item thread-menu-item-danger"
                    role="menuitem"
                    onClick={(e) => handleDeleteClick(e, thread.id)}
                  >
                    Delete
                  </button>
                </div>
              )}

              {/* Inline delete confirmation */}
              {confirmDelete === thread.id && (
                <div className="thread-delete-confirm" onClick={(e) => e.stopPropagation()}>
                  <span className="thread-delete-msg">Delete this thread? This cannot be undone.</span>
                  <div className="thread-delete-actions">
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => setConfirmDelete(null)}
                    >
                      Cancel
                    </button>
                    <button
                      className="btn btn-danger btn-sm"
                      onClick={() => handleDeleteConfirm(thread.id)}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Workspaces</h2>
        <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {workspaces.map((ws) => (
            <li key={ws.workspace_id}>
              <a
                href={`/workspaces/${ws.workspace_id}`}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.5rem",
                  padding: "0.375rem 0.5rem",
                  borderRadius: "0.375rem",
                  fontSize: "0.875rem",
                  color: "var(--text-muted)",
                  textDecoration: "none",
                  transition: "background 0.15s",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surface)")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
              >
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    background: ws.color || "#6366f1",
                    flexShrink: 0,
                  }}
                />
                {ws.icon || "🗂️"} {ws.name}
              </a>
            </li>
          ))}
          <li>
            <a
              href="/workspaces"
              style={{
                display: "block",
                padding: "0.375rem 0.5rem",
                fontSize: "0.8125rem",
                color: "var(--accent)",
                textDecoration: "none",
                opacity: 0.8,
              }}
            >
              {workspaces.length > 0 ? "View all →" : "+ New Workspace"}
            </a>
          </li>
        </ul>
      </section>
    </aside>
  );
}

function MessageRow({ message }: { message: FridayMessage }) {
  const isFriday = message.role === "friday";
  const segments = isFriday ? parseSegments(message.text) : null;
  const [copied, setCopied] = useState(false);
  const genDoc = message.meta?.generated_document as {
    file_id: string; filename: string; mime_type: string;
    size_bytes: number; format: string; download_url: string;
  } | undefined;

  const handleCopy = () => {
    navigator.clipboard.writeText(message.text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <article className={`msg msg-${message.role}`}>
      {isFriday && segments ? (
        segments.map((seg, i) =>
          seg.kind === "diagram" ? (
            <MermaidDiagram key={i} code={seg.code} />
          ) : seg.content.trim() ? (
            <MarkdownMessage key={i} content={seg.content} />
          ) : null
        )
      ) : (
        <p>{message.text}</p>
      )}
      {genDoc && (
        <DocumentCard
          fileId={genDoc.file_id}
          filename={genDoc.filename}
          mimeType={genDoc.mime_type}
          sizeBytes={genDoc.size_bytes}
          format={genDoc.format}
          downloadUrl={genDoc.download_url}
        />
      )}
      <time dateTime={message.timestamp}>{new Date(message.timestamp).toLocaleTimeString()}</time>

      {/* Hover action bar — only on AI messages */}
      {isFriday && (
        <div className="msg-actions" aria-label="Message actions">
          <button
            className="msg-action-btn"
            onClick={handleCopy}
            title="Copy to clipboard"
          >
            {copied ? "✓ Copied" : "Copy"}
          </button>
        </div>
      )}
    </article>
  );
}

const THINKING_STAGES: Record<string, string> = {
  Researching:  "Pulling in context and memory…",
  Working:      "Consulting specialists…",
  Synthesizing: "Drafting the response…",
  Completed:    "",
  Stopped:      "",
  Ready:        "",
  Error:        "",
};

function ThinkingBubble({ label }: { label: string }) {
  const stage = THINKING_STAGES[label] ?? label;
  return (
    <article className="msg msg-friday msg-thinking" aria-busy="true" aria-label="Friday is thinking">
      <div className="thinking-header">
        <span className="thinking-label">Friday is meeting with the team on this</span>
        <span className="thinking-dots" aria-hidden="true">
          <span /><span /><span />
        </span>
      </div>
      {stage ? <p className="thinking-stage">{stage}</p> : null}
    </article>
  );
}

function Transcript({
  messages,
  progress,
  isStreaming
}: {
  messages: FridayMessage[];
  progress: string;
  isStreaming: boolean;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [showJump, setShowJump] = useState(false);

  const lastMsg = messages[messages.length - 1];
  const showThinking = isStreaming && lastMsg?.role === "friday" && lastMsg?.text === "";

  const onScroll = () => {
    const el = containerRef.current;
    if (!el) return;
    const dist = el.scrollHeight - el.scrollTop - el.clientHeight;
    setShowJump(dist > 120);
  };

  const jumpToLatest = () => {
    const el = containerRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    setShowJump(false);
  };

  return (
    <section className="transcript-wrap" aria-label="Conversation transcript">
      <div className="status-bar" role="status" aria-live="polite">
        {progress}
      </div>
      <div className="transcript" role="log" aria-live="polite" aria-relevant="additions text" onScroll={onScroll} ref={containerRef}>
        {messages.map((message) => {
          if (showThinking && message.id === lastMsg.id) {
            return <ThinkingBubble key={message.id} label={progress} />;
          }
          return <MessageRow key={message.id} message={message} />;
        })}
      </div>
      {showJump && (
        <button className="jump-latest" onClick={jumpToLatest}>
          Jump to latest
        </button>
      )}
    </section>
  );
}

function Composer({
  onSend,
  onStop,
  streaming,
  mode,
  setMode,
  chips,
  disabled
}: {
  onSend: (text: string) => void;
  onStop: () => void;
  streaming: boolean;
  mode: ChatMode;
  setMode: (m: ChatMode) => void;
  chips: string[];
  disabled: boolean;
}) {
  const [value, setValue] = useState("");

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    onSend(value);
    setValue("");
  };

  const MODE_TOOLTIPS: Record<ChatMode, string> = {
    ask:  "Get information, analysis, and answers",
    plan: "Build strategies, roadmaps, and structured plans",
    act:  "Execute tasks and make changes with Friday's help",
  };

  return (
    <form className="composer" onSubmit={submit}>
      {/* Segmented mode control — moved into toolbar row */}
      <label htmlFor="composer-input" className="sr-only">
        Message Friday
      </label>
      <textarea
        id="composer-input"
        rows={2}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Ask Friday anything about your business…"
      />
      <div className="chips" aria-label="Context chips">
        {chips.map((chip) => (
          <span key={chip}>{chip}</span>
        ))}
      </div>
      <div className="composer-actions">
        {/* Segmented control — left side */}
        <div className="segmented-control" role="radiogroup" aria-label="Execution mode">
          {(["ask", "plan", "act"] as ChatMode[]).map((opt) => (
            <button
              key={opt}
              type="button"
              role="radio"
              aria-checked={mode === opt}
              className={`segmented-btn${mode === opt ? " segmented-btn-active" : ""}`}
              title={MODE_TOOLTIPS[opt]}
              onClick={() => setMode(opt)}
            >
              {opt.toUpperCase()}
            </button>
          ))}
        </div>

        <button type="button">Attach</button>
        <button type="button">/ Commands</button>
        {!streaming ? (
          <button type="submit" disabled={!value.trim() || disabled}>
            Send
          </button>
        ) : (
          <button type="button" onClick={onStop}>
            Stop
          </button>
        )}
      </div>
    </form>
  );
}

type Approval = {
  approval_id: string;
  request_type: string;
  payload: Record<string, unknown>;
  status: string;
  created_at: string;
};

// Confidence → human-readable label
function confidenceLabel(score: number): string {
  if (score >= 0.85) return "High confidence";
  if (score >= 0.65) return "Moderate confidence";
  return "Review recommended";
}

function RightRail({ lastRunMeta }: { lastRunMeta: { agents: string[]; confidence: number; latency?: number } | null }) {
  const sections = ["This Response", "Experts Consulted", "Sources", "Artifacts", "Approvals"];
  const [expanded, setExpanded] = useState<Record<string, boolean>>({
    "This Response": true,
    "Experts Consulted": true,
  });
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [approvalsLoading, setApprovalsLoading] = useState(false);
  const isDev = process.env.NEXT_PUBLIC_DEV_MODE === "true";

  useEffect(() => {
    setApprovalsLoading(true);
    fetch(`${BACKEND}/approvals`)
      .then((res) => res.json())
      .then((data: unknown) => setApprovals(Array.isArray(data) ? (data as Approval[]) : []))
      .catch(() => setApprovals([]))
      .finally(() => setApprovalsLoading(false));
  }, []);

  const handleApproval = (approvalId: string, action: "approve" | "reject") => {
    fetch(`${BACKEND}/approvals/${approvalId}/${action}`, { method: "POST" })
      .then(() => setApprovals((prev) => prev.filter((a) => a.approval_id !== approvalId)))
      .catch(() => undefined);
  };

  const toggle = (section: string) =>
    setExpanded((prev) => ({ ...prev, [section]: !prev[section] }));

  // Agent key → display name (matches runtime.py _AGENT_DISPLAY_NAMES)
  const DISPLAY_NAMES: Record<string, string> = {
    chief_of_staff_strategist: "Chief of Staff",
    finance: "Finance",
    legal_compliance: "Legal / Compliance",
    hr_people: "HR & People",
    marketing_brand: "Marketing & Brand",
    sales_revenue: "Sales & Revenue",
    operations: "Operations",
    technology: "Technology",
    risk_management: "Risk Management",
    customer_success_support: "Customer Success",
    project_manager: "Project Manager",
    data_analyst: "Data Analyst",
    writer_scribe: "Writer / Scribe",
    executive_coach: "Executive Coach",
    ai_strategy: "AI Strategy",
    internal_comms: "Internal Comms",
    public_relations: "Public Relations",
    mergers_acquisitions: "M&A",
    okr_coach: "OKR Coach",
  };

  return (
    <aside className="right-rail right-rail-scroll" aria-label="Context and trust details">
      {sections.map((section) => {
        const isExpanded = expanded[section] ?? false;

        return (
          <div key={section} className="rail-section">
            <button
              className="rail-section-header"
              onClick={() => toggle(section)}
              aria-expanded={isExpanded}
            >
              <span className="rail-section-title">{section}</span>
              {section === "Approvals" && approvals.length > 0 && (
                <span className="badge badge-warning" style={{ fontSize: "0.6875rem" }}>
                  {approvals.length}
                </span>
              )}
              <span className="rail-section-chevron" aria-hidden="true">
                {isExpanded ? "▾" : "▸"}
              </span>
            </button>

            {isExpanded && (
              <div className="rail-section-body">
                {section === "This Response" && (
                  lastRunMeta ? (
                    <div className="run-status">
                      <div className="run-status-row">
                        <span className="badge badge-success">Completed</span>
                        <span className="run-confidence">{confidenceLabel(lastRunMeta.confidence)}</span>
                      </div>
                      <p className="run-summary">
                        Friday consulted {lastRunMeta.agents.length} specialist{lastRunMeta.agents.length !== 1 ? "s" : ""}.
                      </p>
                      {isDev && (
                        <p className="run-dev-info">
                          Confidence: {(lastRunMeta.confidence * 100).toFixed(0)}%
                          {lastRunMeta.latency != null && ` · ${lastRunMeta.latency.toFixed(1)}s`}
                        </p>
                      )}
                    </div>
                  ) : (
                    <p className="rail-empty">No response yet in this thread.</p>
                  )
                )}

                {section === "Experts Consulted" && (
                  lastRunMeta && lastRunMeta.agents.length > 0 ? (
                    <ul className="rail-list">
                      {lastRunMeta.agents.map((a) => (
                        <li key={a} className="rail-list-item">
                          {DISPLAY_NAMES[a] ?? a}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="rail-empty">No specialists consulted yet.</p>
                  )
                )}

                {section === "Sources" && (
                  <p className="rail-empty">No sources referenced.</p>
                )}

                {section === "Artifacts" && (
                  <p className="rail-empty">No artifacts produced yet.</p>
                )}

                {section === "Approvals" && (
                  approvalsLoading ? (
                    <p className="rail-empty">Loading…</p>
                  ) : approvals.length === 0 ? (
                    <p className="rail-empty">No pending approvals.</p>
                  ) : (
                    <ul>
                      {approvals.map((approval) => (
                        <li key={approval.approval_id} className="approval-item">
                          <span className="approval-type">{approval.request_type}</span>
                          <div className="approval-actions">
                            <button
                              className="btn btn-primary btn-sm"
                              onClick={() => handleApproval(approval.approval_id, "approve")}
                            >
                              Approve
                            </button>
                            <button
                              className="btn btn-danger btn-sm"
                              onClick={() => handleApproval(approval.approval_id, "reject")}
                            >
                              Reject
                            </button>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )
                )}
              </div>
            )}
          </div>
        );
      })}
    </aside>
  );
}

export function Workspace() {
  const {
    threads,
    activeThreadId,
    setActiveThreadId,
    createThread,
    renameThread,
    deleteThread,
    messages,
    send,
    stop,
    isStreaming,
    mode,
    setMode,
    progress,
    connectionState,
    contextChips
  } = useChatState();

  // Track last-run metadata for the right rail
  const lastRunMeta = useMemo(() => {
    const fridayMessages = messages.filter((m) => m.role === "friday" && m.text);
    if (fridayMessages.length === 0) return null;
    const last = fridayMessages[fridayMessages.length - 1];
    const meta = last.meta as { agents?: string[]; confidence?: number; latency?: number } | undefined;
    if (!meta) return null;
    return {
      agents: meta.agents ?? [],
      confidence: meta.confidence ?? 0.72,
      latency: meta.latency,
    };
  }, [messages]);

  const activeThread = threads.find((thread) => thread.id === activeThreadId) ?? threads[0];
  const showReload = !!process.env.NEXT_PUBLIC_ADMIN_API_KEY;
  const [reloadState, setReloadState] = useState<"idle" | "loading" | "ok" | "error">("idle");
  const [reloadMessage, setReloadMessage] = useState("");

  const handleRename = (threadId: string) => {
    const current = threads.find((thread) => thread.id === threadId);
    const proposal = window.prompt("Rename conversation", current?.title ?? "");
    if (!proposal) return;
    renameThread(threadId, proposal);
  };

  const handleDelete = (threadId: string) => {
    deleteThread(threadId);
  };

  const handleReloadRuntime = async () => {
    setReloadState("loading");
    setReloadMessage("Reloading runtime...");
    try {
      const res = await fetch("/api/admin/reload", { method: "POST" });
      const data = (await res.json()) as { error?: string; detail?: string };
      if (!res.ok) {
        const msg = data.error ?? "Reload failed";
        setReloadState("error");
        setReloadMessage(data.detail ? `${msg}: ${data.detail}` : msg);
        return;
      }
      setReloadState("ok");
      setReloadMessage("Runtime reloaded.");
    } catch (error) {
      setReloadState("error");
      setReloadMessage(error instanceof Error ? error.message : "Reload failed");
    }
  };

  return (
    <main className="workspace">
      <LeftRail
        threads={threads}
        activeThreadId={activeThreadId}
        onSelect={setActiveThreadId}
        onCreate={createThread}
        onRename={handleRename}
        onDelete={handleDelete}
      />
      <section className="center-pane" aria-label="Conversation">
        <header className="topbar">
          <h1>{activeThread?.title ?? "Friday"}</h1>
          <div className="topbar-meta">
            <StatusDot state={connectionState} />
            {showReload && (
              <>
                <button
                  type="button"
                  className={`reload-runtime ${reloadState}`}
                  onClick={handleReloadRuntime}
                  disabled={reloadState === "loading"}
                >
                  {reloadState === "loading" ? "Reloading..." : "Reload Runtime"}
                </button>
                {reloadMessage ? (
                  <p className="reload-status" role="status" aria-live="polite">
                    {reloadMessage}
                  </p>
                ) : null}
              </>
            )}
          </div>
        </header>
        <Transcript messages={messages} progress={progress} isStreaming={isStreaming} />
        <Composer
          onSend={send}
          onStop={stop}
          streaming={isStreaming}
          mode={mode}
          setMode={setMode}
          chips={contextChips}
          disabled={connectionState === "offline"}
        />
      </section>
      <RightRail lastRunMeta={lastRunMeta} />
    </main>
  );
}
