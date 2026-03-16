from __future__ import annotations

import re as _re
from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from apps.api.deps import service, admin_auth
from apps.api.security import AuthContext

router = APIRouter()

_AGENT_ID_RE = _re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")


def _auth(request: Request) -> AuthContext:
    return getattr(request.state, "auth", None) or AuthContext(
        user_id="user-1", org_id="org-1", roles=["user"]
    )


class ScaffoldAgentPayload(BaseModel):
    id: str
    name: str
    purpose: str
    owner: str


class EvalPayload(BaseModel):
    suite: str = "core-routing"


@router.get("/agents")
def list_agents() -> dict:
    return {"agents": [asdict(manifest) for manifest in service.registry.list_active()]}


@router.post("/agents/scaffold")
def scaffold_agent(payload: ScaffoldAgentPayload, request: Request) -> dict:
    # PR-06: admin-only + agent_id must be safe (no path traversal).
    admin_auth.require(request)
    admin_auth.audit("agent.scaffold", request, detail=payload.id)
    if not _AGENT_ID_RE.match(payload.id):
        raise HTTPException(
            status_code=400,
            detail="agent id must match ^[a-z0-9][a-z0-9_-]{2,63}$",
        )
    from scripts.create_agent_from_template import create_agent_from_template

    paths = create_agent_from_template(
        agent_id=payload.id,
        name=payload.name,
        purpose=payload.purpose,
        owner=payload.owner,
    )
    return {"status": "created", "paths": paths}


@router.post("/evals/run")
def run_evals(payload: EvalPayload, request: Request) -> dict:
    # PR-06: admin-only — eval runs are expensive and information-revealing.
    admin_auth.require(request)
    admin_auth.audit("evals.run", request, detail=payload.suite or "core-routing")
    suite = payload.suite or "core-routing"
    try:
        report = service.eval_harness.run_suite(suite, service.manager)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return report.to_dict()


@router.get("/admin/dashboard")
def admin_dashboard(request: Request) -> dict:
    admin_auth.require(request)
    return service.get_dashboard_metrics()


@router.get("/admin/tools")
def admin_tools(request: Request) -> dict:
    admin_auth.require(request)
    return {"tools": service.tools.list_tools()}


@router.post("/admin/tools/mcp/register")
def admin_mcp_register(payload: dict, request: Request) -> dict:
    admin_auth.require(request)
    # PR-05: audit all admin mutations.
    admin_auth.audit("mcp.register", request, detail=str(payload.get("server_id", "")))
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


@router.post("/admin/tools/mcp/{server_id}/enable")
def admin_mcp_enable(server_id: str, payload: dict, request: Request) -> dict:
    admin_auth.require(request)
    admin_auth.audit("mcp.enable", request, detail=f"{server_id}={payload.get('enabled')}")
    enabled = bool(payload.get("enabled", True))
    try:
        server = service.mcp.set_enabled(server_id, enabled=enabled)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="server not found") from exc
    return {"server": asdict(server)}


@router.post("/admin/agents/{agent_id}/status")
def admin_agent_status(agent_id: str, payload: dict, request: Request) -> dict:
    admin_auth.require(request)
    admin_auth.audit("agent.status", request, detail=f"{agent_id}={payload.get('status')}")
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


@router.get("/admin/scheduler/jobs")
def list_scheduler_jobs() -> list[dict]:
    """List all registered scheduler jobs."""
    return service.scheduler.list_jobs()


@router.post("/admin/scheduler/jobs/{job_id}/trigger")
def trigger_scheduler_job(job_id: str) -> dict:
    """Manually trigger a scheduled job."""
    try:
        return service.scheduler.trigger_now(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")


@router.post("/admin/runtime/reload")
def admin_runtime_reload(request: Request) -> dict:
    from apps.api.service import FridayService
    admin_auth.require(request)
    global service
    service = FridayService()
    return {"status": "reloaded"}
