from __future__ import annotations

from dataclasses import asdict

from apps.api.service import FridayService
from apps.api.security import AdminAuth, RateLimiter

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse
except ModuleNotFoundError as exc:  # pragma: no cover
    raise RuntimeError(
        "FastAPI is required for apps/api/main.py. Install project dependencies first."
    ) from exc

app = FastAPI(title="Friday API", version="0.2.0")
service = FridayService()
admin_auth = AdminAuth()
rate_limiter = RateLimiter()


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


@app.post("/chat")
def chat(payload: dict) -> dict:
    try:
        return service.execute_chat_payload(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/runs")
def create_run(payload: dict) -> dict:
    def _execute(run_payload: dict) -> dict:
        return chat(run_payload)

    record = service.workflow.run(payload, _execute)
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
def promote_memory_candidate(payload: dict) -> dict:
    candidate_id = str(payload.get("candidate_id") or "").strip()
    if not candidate_id:
        raise HTTPException(status_code=400, detail="candidate_id is required")

    approved = bool(payload.get("approved", False))
    try:
        return service.memory.promote_candidate(candidate_id, approved=approved)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="candidate not found") from exc


@app.get("/agents")
def list_agents() -> dict:
    return {"agents": [asdict(manifest) for manifest in service.registry.list_active()]}


@app.post("/agents/scaffold")
def scaffold_agent(payload: dict) -> dict:
    from scripts.create_agent_from_template import create_agent_from_template

    required = ["id", "name", "purpose", "owner"]
    missing = [field for field in required if not payload.get(field)]
    if missing:
        raise HTTPException(status_code=400, detail=f"missing fields: {', '.join(missing)}")

    paths = create_agent_from_template(
        agent_id=payload["id"],
        name=payload["name"],
        purpose=payload["purpose"],
        owner=payload["owner"],
    )
    return {"status": "created", "paths": paths}


@app.post("/evals/run")
def run_evals(payload: dict) -> dict:
    suite = payload.get("suite") or "core-routing"
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


@app.post("/admin/runtime/reload")
def admin_runtime_reload(request: Request) -> dict:
    admin_auth.require(request)
    global service
    service = FridayService()
    return {"status": "reloaded"}
