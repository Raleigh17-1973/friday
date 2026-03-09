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

      controller.enqueue(enc.encode(sseEvent("response.created", { at: new Date().toISOString() })));
      controller.enqueue(enc.encode(sseEvent("response.in_progress", { label: "Consulting specialists" })));

      try {
        const result = await fetch(`${BACKEND_URL}/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body)
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
          await new Promise((resolve) => setTimeout(resolve, 20));
        }

        controller.enqueue(enc.encode(sseEvent("response.completed", { at: new Date().toISOString() })));
      } catch (error) {
        controller.enqueue(
          enc.encode(
            sseEvent("response.failed", {
              message: error instanceof Error ? error.message : "unknown error"
            })
          )
        );
      } finally {
        controller.close();
      }
    }
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive"
    }
  });
}
