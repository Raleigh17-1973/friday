export type FridayRole = "user" | "friday" | "status" | "approval" | "artifact" | "source";

export type FridayMessage = {
  id: string;
  role: FridayRole;
  text: string;
  timestamp: string;
  meta?: Record<string, unknown>;
};

export type ConversationThread = {
  id: string;
  title: string;
  updatedAt: string;
  parentThreadId?: string;
  branchLabel?: string;
};

export type ConnectionState = "connected" | "reconnecting" | "offline" | "degraded";

export type ChatMode = "ask" | "plan" | "act";
