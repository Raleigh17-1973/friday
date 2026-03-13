from __future__ import annotations

import os
import pathlib
from dataclasses import asdict
from typing import Any

# Load .env from project root before anything else reads os.getenv()
_ROOT = pathlib.Path(__file__).resolve().parents[2]
_dotenv = _ROOT / ".env"
if _dotenv.exists():
    with _dotenv.open() as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip())

from apps.api.service import FridayService
from apps.api.security import AdminAuth, RateLimiter

try:
    from fastapi import FastAPI, File, HTTPException, Request, UploadFile
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel
except ModuleNotFoundError as exc:  # pragma: no cover
    raise RuntimeError(
        "FastAPI is required for apps/api/main.py. Install project dependencies first."
    ) from exc

# In-process upload context store: context_id -> {"filename": str, "text": str, "type": str}
# Lost on restart; use a persistent store (Redis, DB) for production.
_UPLOAD_STORE: dict[str, dict] = {}

app = FastAPI(title="Friday API", version="0.2.0")

# CORS — allow Next.js dev server and same-origin requests
_raw_origins = os.getenv("FRIDAY_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://127.0.0.1:8000")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_UI_DIR = pathlib.Path(__file__).parent.parent.parent / "ui"
if _UI_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_UI_DIR / "assets")), name="static")

    @app.get("/")
    def serve_ui():
        return FileResponse(str(_UI_DIR / "index.html"))

service = FridayService()
admin_auth = AdminAuth()
rate_limiter = RateLimiter()


# --- Pydantic request models ---

class ChatPayload(BaseModel):
    message: str
    user_id: str = "user-1"
    org_id: str = "org-1"
    conversation_id: str = "conv-1"
    context_packet: dict[str, Any] = {}
    # Optional context IDs from POST /upload — injected as context blocks
    context_ids: list[str] = []


class FeedbackPayload(BaseModel):
    approved: bool
    notes: str = ""


class PromoteCandidatePayload(BaseModel):
    candidate_id: str
    approved: bool = False


class ScaffoldAgentPayload(BaseModel):
    id: str
    name: str
    purpose: str
    owner: str


class EvalPayload(BaseModel):
    suite: str = "core-routing"


@app.middleware("http")
async def add_security_and_limits(request: Request, call_next):
    if len(request.url.path) > 2048:
        return JSONResponse({"detail": "path too long"}, status_code=414)

    key = request.client.host if request.client else "unknown"
    rate_limiter.check(key)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict:
    """Readiness probe — checks that all critical dependencies are reachable.

    Used by Fly.io health checks and Kubernetes readiness probes.
    Returns 200 when the service can accept traffic, 503 when not ready.
    """
    checks: dict[str, str] = {}
    ok = True

    # Memory / DB connectivity
    try:
        # Lightweight check: just verify the memory service is initialised
        _ = service.memory  # would raise if initialisation failed
        checks["memory"] = "ok"
    except Exception as exc:
        checks["memory"] = f"error: {exc}"
        ok = False

    # Agent registry
    try:
        agents = service.registry.list_active()
        checks["registry"] = f"ok ({len(agents)} agents)"
    except Exception as exc:
        checks["registry"] = f"error: {exc}"
        ok = False

    # LLM provider (advisory — does not block readiness)
    checks["llm"] = "connected" if service.llm is not None else "offline (stub mode)"

    status_code = 200 if ok else 503
    return JSONResponse(
        content={"status": "ready" if ok else "degraded", "checks": checks},
        status_code=status_code,
    )


@app.post("/chat")
def chat(payload: ChatPayload) -> dict:
    try:
        return service.execute_chat_payload(payload.model_dump(), upload_store=_UPLOAD_STORE)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/chat/stream")
def chat_stream(payload: ChatPayload):
    """Server-sent events endpoint that streams synthesis tokens as they arrive from the LLM.

    SSE event types:
      event: status  — pipeline stage label
      event: token   — one synthesis token chunk
      event: done    — final metadata JSON
      event: error   — error message
    """
    import json as _json
    from packages.common.models import ChatRequest

    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    request = ChatRequest(
        user_id=payload.user_id,
        org_id=payload.org_id,
        conversation_id=payload.conversation_id,
        message=message,
        context_packet=payload.context_packet,
    )

    def _event_generator():
        for evt in service.manager.run_streaming(request):
            event_type = evt.get("event", "message")
            yield f"event: {event_type}\ndata: {_json.dumps(evt)}\n\n"

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@app.post("/runs")
def create_run(payload: ChatPayload) -> dict:
    def _execute(run_payload: dict) -> dict:
        return chat(ChatPayload(**run_payload))

    record = service.workflow.run(payload.model_dump(), _execute)
    return {
        "workflow_id": record.workflow_id,
        "status": record.status,
        "result": record.result,
    }


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    workflow = service.workflow.get(run_id)
    if workflow is not None:
        return {
            "workflow_id": workflow.workflow_id,
            "status": workflow.status,
            "result": workflow.result,
        }

    trace = service.audit.get_run(run_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="run not found")
    return asdict(trace)


@app.post("/runs/{run_id}/feedback")
def run_feedback(run_id: str, payload: FeedbackPayload) -> dict:
    """Record user approval or rejection of a run output.

    The episodic learning loop uses this signal to bias future planning toward
    specialist combinations that have been approved for similar requests.
    """
    try:
        service.manager.record_feedback(run_id, approved=payload.approved, notes=payload.notes)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "recorded", "run_id": run_id, "approved": payload.approved}


@app.post("/approvals/{approval_id}/approve")
def approve(approval_id: str) -> dict:
    try:
        req = service.approvals.approve(approval_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="approval not found") from exc
    return asdict(req)


@app.post("/approvals/{approval_id}/reject")
def reject(approval_id: str) -> dict:
    try:
        req = service.approvals.reject(approval_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="approval not found") from exc
    return asdict(req)


@app.get("/memories/search")
def search_memories(org_id: str, q: str) -> dict:
    return service.memory.search(org_id=org_id, query=q)


@app.post("/memories/candidates/promote")
def promote_memory_candidate(payload: PromoteCandidatePayload) -> dict:
    try:
        return service.memory.promote_candidate(payload.candidate_id, approved=payload.approved)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="candidate not found") from exc


@app.get("/approvals")
def list_approvals(status: str = "pending") -> dict:
    if status == "all":
        items = service.approvals.list_all()
    else:
        items = service.approvals.list_pending()
    return {"approvals": [asdict(r) for r in items]}


@app.get("/conversations")
def list_conversations(user_id: str = "user-1", limit: int = 50) -> dict:
    runs = service.audit.list_runs(limit=limit)
    seen: dict[str, dict] = {}
    for run in runs:
        cid = run.get("conversation_id", "")
        if cid and cid not in seen:
            seen[cid] = {"conversation_id": cid, "user_id": run.get("user_id", ""), "last_run": run.get("run_id")}
    return {"conversations": list(seen.values())}


@app.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str) -> dict:
    service.memory.clear_conversation(conversation_id)
    return {"status": "deleted", "conversation_id": conversation_id}


@app.get("/agents")
def list_agents() -> dict:
    return {"agents": [asdict(manifest) for manifest in service.registry.list_active()]}


@app.post("/agents/scaffold")
def scaffold_agent(payload: ScaffoldAgentPayload) -> dict:
    from scripts.create_agent_from_template import create_agent_from_template

    paths = create_agent_from_template(
        agent_id=payload.id,
        name=payload.name,
        purpose=payload.purpose,
        owner=payload.owner,
    )
    return {"status": "created", "paths": paths}


@app.post("/evals/run")
def run_evals(payload: EvalPayload) -> dict:
    suite = payload.suite or "core-routing"
    try:
        report = service.eval_harness.run_suite(suite, service.manager)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return report.to_dict()


@app.get("/admin/dashboard")
def admin_dashboard(request: Request) -> dict:
    admin_auth.require(request)
    return service.get_dashboard_metrics()


@app.get("/admin/tools")
def admin_tools(request: Request) -> dict:
    admin_auth.require(request)
    return {"tools": service.tools.list_tools()}


@app.post("/admin/tools/mcp/register")
def admin_mcp_register(payload: dict, request: Request) -> dict:
    admin_auth.require(request)
    required = ["server_id", "name", "endpoint"]
    missing = [field for field in required if not payload.get(field)]
    if missing:
        raise HTTPException(status_code=400, detail=f"missing fields: {', '.join(missing)}")

    from packages.tools.mcp import MCPServer

    try:
        server = service.mcp.register(
            MCPServer(
                server_id=str(payload["server_id"]),
                name=str(payload["name"]),
                endpoint=str(payload["endpoint"]),
                auth_type=str(payload.get("auth_type") or "none"),
                enabled=bool(payload.get("enabled", True)),
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"server": asdict(server)}


@app.post("/admin/tools/mcp/{server_id}/enable")
def admin_mcp_enable(server_id: str, payload: dict, request: Request) -> dict:
    admin_auth.require(request)
    enabled = bool(payload.get("enabled", True))
    try:
        server = service.mcp.set_enabled(server_id, enabled=enabled)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="server not found") from exc
    return {"server": asdict(server)}


@app.post("/admin/agents/{agent_id}/status")
def admin_agent_status(agent_id: str, payload: dict, request: Request) -> dict:
    admin_auth.require(request)
    status = str(payload.get("status") or "").strip()
    if not status:
        raise HTTPException(status_code=400, detail="status is required")
    try:
        manifest = service.registry.update_status(agent_id, status)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="agent not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"agent": asdict(manifest)}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)) -> dict:
    """Extract text from an uploaded file and return a context_id.

    Supported types: .txt, .md, .csv, .pdf (requires pypdf), .docx (requires python-docx),
    .png/.jpg/.jpeg/.webp (requires openai — routed to GPT-4o vision).

    Include the returned context_id in the ``context_ids`` field of a /chat request
    to inject the extracted text as specialist context.
    """
    import csv as _csv
    import io
    import uuid

    if not file.filename:
        raise HTTPException(status_code=400, detail="filename is required")

    raw = await file.read()
    name = file.filename.lower()
    ext = name.rsplit(".", 1)[-1] if "." in name else ""

    text = ""
    doc_type = ext

    if ext in ("txt", "md"):
        try:
            text = raw.decode("utf-8", errors="replace")
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Could not decode text file: {exc}") from exc

    elif ext == "csv":
        try:
            reader = _csv.reader(io.StringIO(raw.decode("utf-8", errors="replace")))
            rows = list(reader)
            text = "\n".join(", ".join(row) for row in rows[:500])  # cap at 500 rows
            if len(rows) > 500:
                text += f"\n... ({len(rows) - 500} rows truncated)"
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"CSV parse error: {exc}") from exc

    elif ext == "pdf":
        try:
            import pypdf  # type: ignore
            reader = pypdf.PdfReader(io.BytesIO(raw))
            pages = [page.extract_text() or "" for page in reader.pages]
            text = "\n\n".join(p for p in pages if p.strip())
        except ImportError:
            raise HTTPException(
                status_code=422,
                detail="PDF extraction requires 'pypdf'. Install it: pip install pypdf",
            )
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"PDF parse error: {exc}") from exc

    elif ext == "docx":
        try:
            import docx  # type: ignore
            doc = docx.Document(io.BytesIO(raw))
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except ImportError:
            raise HTTPException(
                status_code=422,
                detail="DOCX extraction requires 'python-docx'. Install it: pip install python-docx",
            )
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"DOCX parse error: {exc}") from exc

    elif ext in ("png", "jpg", "jpeg", "webp", "gif"):
        # Route to GPT-4o vision
        try:
            import base64
            from openai import OpenAI  # type: ignore
            b64 = base64.b64encode(raw).decode("utf-8")
            mime = f"image/{ext if ext != 'jpg' else 'jpeg'}"
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
            resp = client.chat.completions.create(
                model="gpt-4o",
                max_tokens=1000,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                        {"type": "text", "text": "Describe this image in detail. Extract all text, tables, charts, and key information visible."},
                    ],
                }],
            )
            text = resp.choices[0].message.content or ""
            doc_type = "image_vision"
        except ImportError:
            raise HTTPException(status_code=422, detail="Image analysis requires the 'openai' package")
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Vision analysis error: {exc}") from exc

    else:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: .{ext}. Supported: txt, md, csv, pdf, docx, png, jpg, jpeg, webp",
        )

    if not text.strip():
        raise HTTPException(status_code=422, detail="No text could be extracted from the file")

    context_id = f"ctx_{uuid.uuid4().hex[:12]}"
    _UPLOAD_STORE[context_id] = {
        "filename": file.filename,
        "text": text,
        "type": doc_type,
        "chars": len(text),
    }

    return {
        "context_id": context_id,
        "filename": file.filename,
        "type": doc_type,
        "text_length": len(text),
    }


@app.post("/admin/runtime/reload")
def admin_runtime_reload(request: Request) -> dict:
    admin_auth.require(request)
    global service
    service = FridayService()
    return {"status": "reloaded"}
