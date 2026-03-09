# Friday Web Workspace

Premium conversation workspace for Friday using Next.js + TypeScript.

## Implemented in this scaffold
- Three-zone desktop layout (left rail / conversation / right trust rail)
- Mobile single-pane fallback
- Transcript-first UI with `role="log"`
- Streaming composer with Ask / Plan / Act modes
- Stop generation control
- Context chips and attachment-ready controls
- Jump-to-latest affordance when scrolled away
- Right rail tabs for context, experts, sources, artifacts, approvals, and run details
- Reduced-motion support and strong visible focus styles
- Safe-area-aware composer padding

## API routes
- `POST /api/chat`:
  - Proxies to Friday backend `/chat`
  - Streams lifecycle events in SSE format (`response.created`, `response.in_progress`, deltas, `response.completed`)
- `POST /api/chatkit/session`:
  - Server-side session creation for ChatKit using `OPENAI_API_KEY`
  - Returns session payload from OpenAI

## Run
```bash
cd apps/web
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

Set env vars if needed:
- `FRIDAY_BACKEND_URL` (default `http://127.0.0.1:8000`)
- `OPENAI_API_KEY` (required for `/api/chatkit/session`)
