"use client";

import { useMemo, useRef, useState } from "react";

import { useChatState } from "@/components/use-chat-state";
import type { ChatMode, ConversationThread, FridayMessage } from "@/lib/types";

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

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return threads;
    return threads.filter((thread) => thread.title.toLowerCase().includes(q));
  }, [threads, query]);

  return (
    <aside className="left-rail" aria-label="Threads and saved context">
      <header className="rail-header">Friday</header>
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
            <li key={thread.id} className={thread.id === activeThreadId ? "active" : ""}>
              <button className="thread-title" onClick={() => onSelect(thread.id)}>
                {thread.title}
              </button>
              <div className="thread-actions">
                <button aria-label={`Rename ${thread.title}`} onClick={() => onRename(thread.id)}>
                  Rename
                </button>
                <button aria-label={`Delete ${thread.title}`} onClick={() => onDelete(thread.id)}>
                  Delete
                </button>
              </div>
            </li>
          ))}
        </ul>
      </section>
      <section>
        <h2>Pinned Workspaces</h2>
        <ul>
          <li>Operating Plan</li>
          <li>Go-to-market</li>
        </ul>
      </section>
      <section>
        <h2>Saved Artifacts</h2>
        <ul>
          <li>Exec Memo v3</li>
          <li>Risk Register</li>
        </ul>
      </section>
    </aside>
  );
}

function MessageRow({ message }: { message: FridayMessage }) {
  return (
    <article className={`msg msg-${message.role}`}>
      <p>{message.text}</p>
      <time dateTime={message.timestamp}>{new Date(message.timestamp).toLocaleTimeString()}</time>
    </article>
  );
}

function Transcript({ messages, progress }: { messages: FridayMessage[]; progress: string }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [showJump, setShowJump] = useState(false);

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
        {messages.map((message) => (
          <MessageRow key={message.id} message={message} />
        ))}
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

  return (
    <form className="composer" onSubmit={submit}>
      <div className="mode-toggle" role="radiogroup" aria-label="Execution mode">
        {(["ask", "plan", "act"] as ChatMode[]).map((opt) => (
          <button
            key={opt}
            type="button"
            role="radio"
            aria-checked={mode === opt}
            className={mode === opt ? "selected" : ""}
            onClick={() => setMode(opt)}
          >
            {opt.toUpperCase()}
          </button>
        ))}
      </div>
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

function RightRail() {
  const tabs = ["Context", "Experts", "Sources", "Artifacts", "Approvals", "Run"];
  const [active, setActive] = useState(tabs[0]);

  const panel = useMemo(() => {
    if (active === "Experts") return ["Consulted Finance", "Consulted Operations", "Red-team pass complete"];
    if (active === "Sources") return ["Q1 board memo", "Pricing dashboard", "Pipeline exports"];
    if (active === "Approvals") return ["No pending approvals"];
    if (active === "Artifacts") return ["Exec summary", "Action checklist", "Risk table"];
    if (active === "Run") return ["State: completed", "Latency: 2.4s", "Confidence: 0.72"];
    return ["Active workspace: Default", "Pinned memory: ROI discipline", "Mode: Ask/Plan/Act"];
  }, [active]);

  return (
    <aside className="right-rail" aria-label="Context and trust details">
      <nav aria-label="Right rail tabs">
        {tabs.map((tab) => (
          <button key={tab} className={active === tab ? "active" : ""} onClick={() => setActive(tab)}>
            {tab}
          </button>
        ))}
      </nav>
      <ul>
        {panel.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
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

  const activeThread = threads.find((thread) => thread.id === activeThreadId) ?? threads[0];
  const [reloadState, setReloadState] = useState<"idle" | "loading" | "ok" | "error">("idle");
  const [reloadMessage, setReloadMessage] = useState("");

  const handleRename = (threadId: string) => {
    const current = threads.find((thread) => thread.id === threadId);
    const proposal = window.prompt("Rename conversation", current?.title ?? "");
    if (!proposal) return;
    renameThread(threadId, proposal);
  };

  const handleDelete = (threadId: string) => {
    const ok = window.confirm("Delete this conversation?");
    if (!ok) return;
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
            <p role="status" aria-live="polite">
              Connection: {connectionState}
            </p>
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
          </div>
        </header>
        <Transcript messages={messages} progress={progress} />
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
      <RightRail />
    </main>
  );
}
