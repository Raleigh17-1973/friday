import { NextRequest } from "next/server";

const BACKEND_URL = process.env.FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000";

function sseEvent(event: string, data: Record<string, unknown>) {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

export async function POST(req: NextRequest) {
  const body = await req.json();

  const stream = new ReadableStream({
    async start(controller) {
      const enc = new TextEncoder();

      // Try the streaming endpoint first — gives real token-by-token output
      try {
        const backendStream = await fetch(`${BACKEND_URL}/chat/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });

        if (!backendStream.ok || !backendStream.body) {
          throw new Error(`Backend stream failed: ${backendStream.status}`);
        }

        // Proxy the SSE stream directly, translating backend events to frontend events
        const reader = backendStream.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        controller.enqueue(enc.encode(sseEvent("response.created", { at: new Date().toISOString() })));

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split("\n\n");
          buffer = parts.pop() ?? "";

          for (const part of parts) {
            const lines = part.trim().split("\n");
            let eventType = "message";
            let dataStr = "";

            for (const line of lines) {
              if (line.startsWith("event: ")) eventType = line.slice(7).trim();
              if (line.startsWith("data: ")) dataStr = line.slice(6).trim();
            }

            if (!dataStr) continue;

            let parsed: Record<string, unknown>;
            try {
              parsed = JSON.parse(dataStr);
            } catch {
              continue;
            }

            // Map backend events → frontend SSE events
            if (eventType === "status") {
              controller.enqueue(enc.encode(sseEvent("response.in_progress", { label: parsed.label ?? "" })));
            } else if (eventType === "token") {
              controller.enqueue(enc.encode(sseEvent("response.output_text.delta", { text: parsed.text ?? "" })));
            } else if (eventType === "done") {
              controller.enqueue(enc.encode(sseEvent("response.completed", { at: new Date().toISOString(), ...parsed })));
            } else if (eventType === "error") {
              controller.enqueue(enc.encode(sseEvent("response.failed", { message: parsed.message ?? "Unknown error" })));
            }
          }
        }
      } catch (streamErr) {
        // Fall back to non-streaming /chat endpoint
        try {
          controller.enqueue(enc.encode(sseEvent("response.in_progress", { label: "Consulting specialists" })));

          const result = await fetch(`${BACKEND_URL}/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          });

          if (!result.ok) {
            controller.enqueue(enc.encode(sseEvent("response.failed", { message: `Backend failed: ${result.status}` })));
            controller.close();
            return;
          }

          const data = await result.json();
          const text = String(data?.final_answer?.direct_answer ?? data?.response ?? "");

          controller.enqueue(enc.encode(sseEvent("response.in_progress", { label: "Drafting response" })));
          for (const token of text.split(" ")) {
            controller.enqueue(enc.encode(sseEvent("response.output_text.delta", { text: `${token} ` })));
          }

          const completedPayload: Record<string, unknown> = { at: new Date().toISOString() };
          if (data?.generated_document) {
            completedPayload.generated_document = data.generated_document;
          }
          controller.enqueue(enc.encode(sseEvent("response.completed", completedPayload)));
        } catch (fallbackErr) {
          controller.enqueue(
            enc.encode(
              sseEvent("response.failed", {
                message: fallbackErr instanceof Error ? fallbackErr.message : "unknown error",
              })
            )
          );
        }
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
