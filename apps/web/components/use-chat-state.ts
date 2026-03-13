"use client";

import { useEffect } from "react";
import { useMemo, useRef, useState } from "react";

import type { ChatMode, ConnectionState, ConversationThread, FridayMessage } from "@/lib/types";

function id() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function nowIso() {
  return new Date().toISOString();
}

function titleFromText(text: string) {
  const trimmed = text.trim();
  if (!trimmed) return "New chat";
  const normalized = trimmed.replace(/\s+/g, " ");
  return normalized.length > 42 ? `${normalized.slice(0, 42)}…` : normalized;
}

const STORAGE_KEY = "friday_web_state_v1";
const BACKEND = process.env.NEXT_PUBLIC_FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000";

type PersistedState = {
  threads: ConversationThread[];
  activeThreadId: string;
  messagesByThread: Record<string, FridayMessage[]>;
  mode: ChatMode;
  contextChips: string[];
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
  const [contextChips] = useState<string[]>(["Workspace: Default"]);
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
      contextChips,
    };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  }, [hydrated, threads, activeThreadId, messagesByThread, mode, contextChips]);

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

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "web-user",
          org_id: "web-org",
          conversation_id: threadId,
          message: text,
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
          };

          if (eventName === "response.in_progress") {
            setProgress(data.label ?? "Working");
          }
          if (eventName === "response.output_text.delta" && data.text) {
            updateThreadMessages(threadId, (prev) =>
              prev.map((msg) => (msg.id === runMsgId ? { ...msg, text: `${msg.text}${data.text}` } : msg))
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
    contextChips
  };
}
