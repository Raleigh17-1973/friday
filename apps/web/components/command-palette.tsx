"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { ConversationThread } from "@/lib/types";

// ── Types ─────────────────────────────────────────────────────────────────
type ResultKind = "thread" | "page" | "action" | "okr" | "doc";

type PaletteResult = {
  id: string;
  kind: ResultKind;
  label: string;
  sublabel?: string;
  icon: string;
  href?: string;
  onSelect?: () => void;
};

const KIND_ORDER: ResultKind[] = ["page", "action", "thread", "okr", "doc"];
const KIND_LABEL: Record<ResultKind, string> = {
  page:   "Navigation",
  action: "Actions",
  thread: "Threads",
  okr:    "OKRs",
  doc:    "Documents",
};

// Static pages
const PAGES: PaletteResult[] = [
  { id: "p-chat",       kind: "page", icon: "💬", label: "Chat",           href: "/" },
  { id: "p-processes",  kind: "page", icon: "⚙",  label: "Process Library", href: "/processes" },
  { id: "p-docs",       kind: "page", icon: "📄", label: "Documents",       href: "/documents" },
  { id: "p-analytics",  kind: "page", icon: "📊", label: "Analytics",       href: "/analytics" },
  { id: "p-okrs",       kind: "page", icon: "🎯", label: "OKRs",            href: "/okrs" },
  { id: "p-workspaces", kind: "page", icon: "🗂", label: "Workspaces",      href: "/workspaces" },
  { id: "p-settings",   kind: "page", icon: "⚙",  label: "Settings",        href: "/settings" },
  { id: "p-memory",     kind: "page", icon: "🧠", label: "Memory",          href: "/settings/memory" },
];

// ── Component ─────────────────────────────────────────────────────────────
export function CommandPalette({
  threads,
  onSelectThread,
  onNewChat,
  onClose,
}: {
  threads: ConversationThread[];
  onSelectThread: (id: string) => void;
  onNewChat: () => void;
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");
  const [activeIdx, setActiveIdx] = useState(0);
  const [okrs, setOkrs] = useState<PaletteResult[]>([]);
  const [docs, setDocs] = useState<PaletteResult[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const BACKEND = process.env.NEXT_PUBLIC_FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000";

  // Focus input on mount
  useEffect(() => { inputRef.current?.focus(); }, []);

  // Fetch OKRs and docs when query changes (debounced 300ms)
  useEffect(() => {
    if (query.trim().length < 2) { setOkrs([]); setDocs([]); return; }
    const t = setTimeout(() => {
      const q = encodeURIComponent(query.trim());
      fetch(`${BACKEND}/okrs?org_id=default&q=${q}`)
        .then((r) => r.ok ? r.json() : [])
        .then((data: unknown[]) => {
          if (!Array.isArray(data)) return;
          setOkrs(data.slice(0, 4).map((raw: unknown, i: number) => {
            const o = raw as Record<string, unknown>;
            return {
              id: `okr-${i}`,
              kind: "okr" as ResultKind,
              icon: "🎯",
              label: String(o.title ?? "Objective"),
              sublabel: String(o.status ?? ""),
              href: `/okrs/${o.obj_id}`,
            };
          }));
        })
        .catch(() => setOkrs([]));

      fetch(`${BACKEND}/files`)
        .then((r) => r.ok ? r.json() : { files: [] })
        .then((data: { files?: Record<string, unknown>[] }) => {
          const files = Array.isArray(data?.files) ? data.files : [];
          const q2 = query.trim().toLowerCase();
          const filtered = files
            .filter((f) => String(f.filename ?? "").toLowerCase().includes(q2))
            .slice(0, 4);
          setDocs(filtered.map((f, i) => ({
            id: `doc-${i}`,
            kind: "doc" as ResultKind,
            icon: "📄",
            label: String(f.filename ?? "Document"),
            sublabel: String(f.mime_type ?? ""),
            href: `/documents`,
          })));
        })
        .catch(() => setDocs([]));
    }, 300);
    return () => clearTimeout(t);
  }, [query, BACKEND]);

  const results = useMemo((): PaletteResult[] => {
    const q = query.trim().toLowerCase();

    const staticActions: PaletteResult[] = [
      { id: "a-new-chat", kind: "action", icon: "+", label: "New Chat", onSelect: () => { onNewChat(); onClose(); } },
    ];

    const pageResults = PAGES.filter(
      (p) => !q || p.label.toLowerCase().includes(q)
    );
    const actionResults = staticActions.filter(
      (a) => !q || a.label.toLowerCase().includes(q)
    );
    const threadResults = threads
      .filter((t) => !q || t.title.toLowerCase().includes(q))
      .slice(0, 6)
      .map((t) => ({
        id: t.id,
        kind: "thread" as ResultKind,
        icon: "💬",
        label: t.title,
        sublabel: new Date(t.updatedAt).toLocaleDateString(),
        onSelect: () => { onSelectThread(t.id); onClose(); },
      }));

    return [...pageResults, ...actionResults, ...threadResults, ...okrs, ...docs];
  }, [query, threads, okrs, docs, onNewChat, onClose, onSelectThread]);

  // Reset active idx when results change
  useEffect(() => { setActiveIdx(0); }, [results]);

  // Scroll active item into view
  useEffect(() => {
    const el = listRef.current?.children[activeIdx] as HTMLElement | undefined;
    el?.scrollIntoView({ block: "nearest" });
  }, [activeIdx]);

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setActiveIdx((i) => Math.min(i + 1, results.length - 1)); }
    if (e.key === "ArrowUp")   { e.preventDefault(); setActiveIdx((i) => Math.max(i - 1, 0)); }
    if (e.key === "Enter") { e.preventDefault(); selectResult(results[activeIdx]); }
    if (e.key === "Escape") onClose();
  };

  const selectResult = (r: PaletteResult | undefined) => {
    if (!r) return;
    if (r.onSelect) { r.onSelect(); return; }
    if (r.href) { window.location.href = r.href; onClose(); }
  };

  // Group results by kind for display
  const grouped = useMemo(() => {
    const groups: { kind: ResultKind; items: PaletteResult[] }[] = [];
    for (const kind of KIND_ORDER) {
      const items = results.filter((r) => r.kind === kind);
      if (items.length) groups.push({ kind, items });
    }
    return groups;
  }, [results]);

  // Flat index for keyboard nav across groups
  const flatResults = useMemo(() => results, [results]);

  return (
    <div className="cmd-overlay" onClick={onClose} role="dialog" aria-modal="true" aria-label="Command palette">
      <div className="cmd-palette" onClick={(e) => e.stopPropagation()} onKeyDown={handleKey}>
        <div className="cmd-input-row">
          <span className="cmd-search-icon" aria-hidden="true">⌕</span>
          <input
            ref={inputRef}
            className="cmd-input"
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search threads, pages, OKRs…"
            aria-label="Search"
          />
          <kbd className="cmd-esc-hint">Esc</kbd>
        </div>

        {flatResults.length === 0 ? (
          <div className="cmd-empty">No results for &ldquo;{query}&rdquo;</div>
        ) : (
          <ul className="cmd-results" ref={listRef} role="listbox">
            {grouped.map(({ kind, items }) => {
              // Find global offset of first item in this group
              const groupOffset = flatResults.findIndex((r) => r.id === items[0].id);
              return (
                <li key={kind} role="presentation">
                  <div className="cmd-group-label">{KIND_LABEL[kind]}</div>
                  <ul role="presentation">
                    {items.map((result, i) => {
                      const globalIdx = groupOffset + i;
                      const isActive = globalIdx === activeIdx;
                      return (
                        <li
                          key={result.id}
                          role="option"
                          aria-selected={isActive}
                          className={`cmd-item${isActive ? " cmd-item-active" : ""}`}
                          onMouseEnter={() => setActiveIdx(globalIdx)}
                          onClick={() => selectResult(result)}
                        >
                          <span className="cmd-item-icon" aria-hidden="true">{result.icon}</span>
                          <span className="cmd-item-body">
                            <span className="cmd-item-label">{result.label}</span>
                            {result.sublabel && (
                              <span className="cmd-item-sublabel">{result.sublabel}</span>
                            )}
                          </span>
                          {result.href && <span className="cmd-item-arrow" aria-hidden="true">↗</span>}
                        </li>
                      );
                    })}
                  </ul>
                </li>
              );
            })}
          </ul>
        )}

        <div className="cmd-footer">
          <span><kbd>↑↓</kbd> Navigate</span>
          <span><kbd>↵</kbd> Open</span>
          <span><kbd>Esc</kbd> Close</span>
        </div>
      </div>
    </div>
  );
}
