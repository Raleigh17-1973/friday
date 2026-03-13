"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { ChatMode, ConnectionState, ConversationThread, FridayMessage } from "@/lib/types";

function id() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function nowIso() {
  return new Date().toISOString();
}

// Strip common filler prefixes before making a title, then break at a word boundary.
const FILLER_RE = /^(please\s+|can you\s+|could you\s+|i want to\s+|i need to\s+|i'd like to\s+|i would like to\s+|help me\s+|help me to\s+)/i;

function titleFromText(text: string) {
  const trimmed = text.trim().replace(/\s+/g, " ");
  if (!trimmed) return "New chat";
  // Strip filler prefix so titles are more meaningful
  const stripped = trimmed.replace(FILLER_RE, "");
  const candidate = stripped.charAt(0).toUpperCase() + stripped.slice(1);
  if (candidate.length <= 52) return candidate;
  // Break at last word boundary before char 52
  const cut = candidate.slice(0, 52);
  const lastSpace = cut.lastIndexOf(" ");
  return lastSpace > 18 ? `${cut.slice(0, lastSpace)}…` : `${cut}…`;
}

const STORAGE_KEY = "friday_web_state_v1";
const BACKEND = process.env.NEXT_PUBLIC_FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000";

type PersistedState = {
  threads: ConversationThread[];
  activeThreadId: string;
  messagesByThread: Record<string, FridayMessage[]>;
  mode: ChatMode;
  contextChips: string[];
  activeWorkspaceId: string;
  activeWorkspaceName: string;
};

export function useChatState() {
  const initialThread: ConversationThread = {
    id: id(),
    title: "New chat",
    updatedAt: nowIso()
  };

  const [threads, setThreads] = useState<ConversationThread[]>([initialThread]);
  const [activeThreadId, setActiveThreadId] = useState(initialThread.id);
  const [messagesByThread, setMessagesByThread] = useState<Record<string, FridayMessage[]>>({
    [initialThread.id]: []
  });

  const [isStreaming, setIsStreaming] = useState(false);
  const [connectionState, setConnectionState] = useState<ConnectionState>("connected");
  const [mode, setMode] = useState<ChatMode>("ask");
  const [progress, setProgress] = useState("Ready");
  const [activeWorkspaceId, setActiveWorkspaceId] = useState("default");
  const [activeWorkspaceName, setActiveWorkspaceName] = useState("Default");
  const controllerRef = useRef<AbortController | null>(null);
  const [hydrated, setHydrated] = useState(false);

  const messages = useMemo(
    () => messagesByThread[activeThreadId] ?? [],
    [activeThreadId, messagesByThread]
  );

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) {
        setHydrated(true);
        return;
      }
      const parsed = JSON.parse(raw) as Partial<PersistedState>;
      if (parsed.threads && parsed.threads.length > 0) {
        setThreads(parsed.threads);
      }
      if (parsed.messagesByThread) {
        setMessagesByThread(parsed.messagesByThread);
      }
      if (parsed.activeThreadId) {
        setActiveThreadId(parsed.activeThreadId);
      }
      if (parsed.mode) {
        setMode(parsed.mode);
      }
      if (parsed.activeWorkspaceId) {
        setActiveWorkspaceId(parsed.activeWorkspaceId);
        setActiveWorkspaceName(parsed.activeWorkspaceName ?? "Default");
      }
      setHydrated(true);
    } catch {
      setHydrated(true);
    }
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    const payload: PersistedState = {
      threads,
      activeThreadId,
      messagesByThread,
      mode,
      contextChips: [],
      activeWorkspaceId,
      activeWorkspaceName,
    };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  }, [hydrated, threads, activeThreadId, messagesByThread, mode, activeWorkspaceId, activeWorkspaceName]);

  const canSend = useMemo(() => !isStreaming && connectionState !== "offline", [isStreaming, connectionState]);

  const touchThread = (threadId: string, fallbackTitle?: string) => {
    setThreads((prev) =>
      prev
        .map((thread) => {
          if (thread.id !== threadId) return thread;
          const nextTitle =
            thread.title === "New chat" && fallbackTitle ? titleFromText(fallbackTitle) : thread.title;
          return { ...thread, title: nextTitle, updatedAt: nowIso() };
        })
        .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
    );
  };

  const updateThreadMessages = (
    threadId: string,
    updater: (current: FridayMessage[]) => FridayMessage[]
  ) => {
    setMessagesByThread((prev) => {
      const current = prev[threadId] ?? [];
      return { ...prev, [threadId]: updater(current) };
    });
  };

  const createThread = () => {
    const thread: ConversationThread = { id: id(), title: "New chat", updatedAt: nowIso() };
    setThreads((prev) => [thread, ...prev]);
    setMessagesByThread((prev) => ({ ...prev, [thread.id]: [] }));
    setActiveThreadId(thread.id);
    setProgress("Ready");
  };

  const renameThread = (threadId: string, title: string) => {
    const clean = title.trim();
    if (!clean) return;
    setThreads((prev) => prev.map((thread) => (thread.id === threadId ? { ...thread, title: clean } : thread)));
  };

  const deleteThread = (threadId: string) => {
    setThreads((prev) => {
      if (prev.length === 1) {
        const only = prev[0];
        setMessagesByThread({ [only.id]: [] });
        setProgress("Ready");
        return [{ ...only, title: "New chat", updatedAt: nowIso() }];
      }

      const next = prev.filter((thread) => thread.id !== threadId);
      if (activeThreadId === threadId && next[0]) {
        setActiveThreadId(next[0].id);
      }
      return next;
    });
    setMessagesByThread((prev) => {
      const copy = { ...prev };
      delete copy[threadId];
      return copy;
    });
    fetch(`${BACKEND}/conversations/${threadId}`, { method: "DELETE" }).catch(() => undefined);
  };

  const stop = () => {
    controllerRef.current?.abort();
    controllerRef.current = null;
    setIsStreaming(false);
    setProgress("Stopped");
  };

  // Send feedback (thumbs up/down) for a completed run
  const sendFeedback = useCallback((runId: string, approved: boolean) => {
    fetch(`${BACKEND}/runs/${runId}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approved, notes: "" }),
    }).catch(() => undefined);
  }, []);

  // Set active workspace
  const setActiveWorkspace = useCallback((wsId: string, wsName: string) => {
    setActiveWorkspaceId(wsId);
    setActiveWorkspaceName(wsName);
  }, []);

  const send = async (input: string) => {
    const text = input.trim();
    if (!text || !canSend) return;

    const threadId = activeThreadId;
    touchThread(threadId, text);

    const userMsg: FridayMessage = {
      id: id(),
      role: "user",
      text,
      timestamp: nowIso()
    };
    updateThreadMessages(threadId, (prev) => [...prev, userMsg]);

    const runMsgId = id();
    updateThreadMessages(threadId, (prev) => [
      ...prev,
      { id: runMsgId, role: "friday", text: "", timestamp: nowIso() }
    ]);

    setIsStreaming(true);
    setConnectionState("connected");
    setProgress("Researching");

    const controller = new AbortController();
    controllerRef.current = controller;

    // Snapshot current message count to detect "first exchange"
    const msgsBefore = (messagesByThread[threadId] ?? []).length;

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "web-user",
          org_id: "web-org",
          conversation_id: threadId,
          message: text,
          workspace_id: activeWorkspaceId !== "default" ? activeWorkspaceId : undefined,
          context_packet: { mode }
        }),
        signal: controller.signal
      });

      if (!res.ok || !res.body) {
        throw new Error(`Chat failed: ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const chunks = buffer.split("\n\n");
        buffer = chunks.pop() ?? "";

        for (const chunk of chunks) {
          const lines = chunk.split("\n");
          const eventLine = lines.find((line) => line.startsWith("event:"));
          const dataLine = lines.find((line) => line.startsWith("data:"));
          if (!eventLine || !dataLine) continue;

          const eventName = eventLine.replace("event:", "").trim();
          const data = JSON.parse(dataLine.replace("data:", "").trim()) as {
            text?: string;
            label?: string;
            message?: string;
            run_id?: string;
            selected_agents?: string[];
            confidence?: number;
            generated_document?: {
              file_id: string;
              filename: string;
              mime_type: string;
              size_bytes: number;
              format: string;
              download_url: string;
            };
          };

          if (eventName === "response.in_progress") {
            setProgress(data.label ?? "Working");
          }
          if (eventName === "response.output_text.delta" && data.text) {
            updateThreadMessages(threadId, (prev) =>
              prev.map((msg) => (msg.id === runMsgId ? { ...msg, text: `${msg.text}${data.text}` } : msg))
            );
          }
          if (eventName === "response.completed") {
            // Capture run metadata into the message so the right panel and action bar can use it
            const metaUpdate: Record<string, unknown> = {};
            if (data.run_id) metaUpdate.run_id = data.run_id;
            if (data.selected_agents) metaUpdate.agents = data.selected_agents;
            if (data.confidence != null) metaUpdate.confidence = data.confidence;
            if (data.generated_document) metaUpdate.generated_document = data.generated_document;

            updateThreadMessages(threadId, (prev) =>
              prev.map((msg) =>
                msg.id === runMsgId
                  ? { ...msg, meta: { ...msg.meta, ...metaUpdate } }
                  : msg
              )
            );
          }
          if (eventName === "response.failed") {
            updateThreadMessages(threadId, (prev) =>
              prev.map((msg) =>
                msg.id === runMsgId
                  ? { ...msg, role: "status", text: data.message ?? "Request failed." }
                  : msg
              )
            );
            setConnectionState("degraded");
          }
        }
      }

      touchThread(threadId);
      setProgress("Completed");

      // Auto-generate a smarter title after the very first exchange in a new thread
      // msgsBefore === 0 means this was a fresh thread with no prior messages
      if (msgsBefore === 0) {
        const currentThread = threads.find((t) => t.id === threadId);
        if (currentThread && (currentThread.title === "New chat" || currentThread.title === titleFromText(text))) {
          // The titleFromText already ran on send — it already improved the title.
          // If backend title generation is desired in future, fire it here as a background task.
          // For now, the word-boundary-aware titleFromText is good enough.
        }
      }
    } catch (error) {
      setConnectionState("degraded");
      setProgress("Error");
      updateThreadMessages(threadId, (prev) => [
        ...prev,
        {
          id: id(),
          role: "status",
          text: `Error: ${error instanceof Error ? error.message : "Unknown"}`,
          timestamp: nowIso()
        }
      ]);
    } finally {
      controllerRef.current = null;
      setIsStreaming(false);
    }
  };

  return {
    threads,
    activeThreadId,
    setActiveThreadId,
    createThread,
    renameThread,
    deleteThread,
    messages,
    isStreaming,
    send,
    stop,
    mode,
    setMode,
    progress,
    connectionState,
    activeWorkspaceId,
    activeWorkspaceName,
    setActiveWorkspace,
    sendFeedback,
  };
}
