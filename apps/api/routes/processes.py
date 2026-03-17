from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from apps.api.deps import service
from apps.api.security import AuthContext

router = APIRouter()


def _auth(request: Request) -> AuthContext:
    return getattr(request.state, "auth", None) or AuthContext(
        user_id="user-1", org_id="org-1", roles=["user"]
    )


def _process_for_auth(process_id: str, auth: AuthContext):
    doc = service.processes.get(process_id)
    if doc is None or doc.org_id != auth.org_id:
        raise HTTPException(status_code=404, detail="Process not found")
    return doc


def _run_for_auth(run_id: str, auth: AuthContext) -> dict:
    run = service.processes._repo.get_execution_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Execution run not found")
    _process_for_auth(run["process_id"], auth)
    return run


class ProcessCreatePayload(BaseModel):
    org_id: str = "org-1"
    process_name: str
    trigger: str = ""
    steps: list[dict] = []
    decision_points: list[dict] = []
    roles: list[str] = []
    tools: list[str] = []
    exceptions: list[dict] = []
    kpis: list[dict] = []
    mermaid_flowchart: str = ""
    mermaid_swimlane: str = ""
    status: str = "draft"


class ProcessUpdatePayload(BaseModel):
    bump: str = "patch"           # major | minor | patch
    author: str = "user"
    changelog_entry: str = ""
    # fields to update (any subset)
    process_name: Optional[str] = None
    trigger: Optional[str] = None
    steps: Optional[list] = None
    decision_points: Optional[list] = None
    roles: Optional[list] = None
    tools: Optional[list] = None
    exceptions: Optional[list] = None
    kpis: Optional[list] = None
    mermaid_flowchart: Optional[str] = None
    mermaid_swimlane: Optional[str] = None
    status: Optional[str] = None


@router.get("/processes")
def list_processes(request: Request, org_id: str = "org-1") -> list[dict]:
    auth = _auth(request)
    docs = service.processes.list(org_id=auth.org_id)
    return [d.to_dict() for d in docs]


@router.post("/processes", status_code=201)
def create_process(payload: ProcessCreatePayload, request: Request) -> dict:
    from packages.common.models import ProcessDocument, ProcessStep
    auth = _auth(request)
    steps = [ProcessStep(**s) if isinstance(s, dict) else s for s in payload.steps]
    doc = ProcessDocument(
        id="",
        org_id=auth.org_id,
        process_name=payload.process_name,
        trigger=payload.trigger,
        steps=steps,
        decision_points=payload.decision_points,
        roles=payload.roles,
        tools=payload.tools,
        exceptions=payload.exceptions,
        kpis=payload.kpis,
        mermaid_flowchart=payload.mermaid_flowchart,
        mermaid_swimlane=payload.mermaid_swimlane,
        completeness_score=0.0,
        status=payload.status,
    )
    created = service.processes.create(doc)
    return created.to_dict()


@router.get("/processes/analytics")
def process_analytics(request: Request, org_id: str = "org-1") -> dict:
    auth = _auth(request)
    return service.process_analytics.org_health(org_id=auth.org_id)


@router.get("/processes/{process_id}")
def get_process(process_id: str, request: Request) -> dict:
    auth = _auth(request)
    doc = _process_for_auth(process_id, auth)
    return doc.to_dict()


@router.put("/processes/{process_id}")
def update_process(process_id: str, payload: ProcessUpdatePayload, request: Request) -> dict:
    auth = _auth(request)
    changes: dict = {}
    for field in ("process_name", "trigger", "steps", "decision_points",
                  "roles", "tools", "exceptions", "kpis",
                  "mermaid_flowchart", "mermaid_swimlane", "status"):
        val = getattr(payload, field, None)
        if val is not None:
            changes[field] = val
    if not changes:
        raise HTTPException(status_code=400, detail="No changes provided")
    try:
        _process_for_auth(process_id, auth)
        result = service.processes.update(
            process_id,
            changes=changes,
            bump=payload.bump,
            author=auth.user_id,
            changelog_entry=payload.changelog_entry,
        )
        # Major bump held for approval — return 202 Accepted with pending payload
        if isinstance(result, dict) and result.get("status") == "pending_approval":
            return JSONResponse(status_code=202, content=result)
        return result.to_dict()
    except KeyError:
        raise HTTPException(status_code=404, detail="Process not found")


@router.delete("/processes/{process_id}", status_code=204)
def delete_process(process_id: str, request: Request) -> None:
    auth = _auth(request)
    _process_for_auth(process_id, auth)
    service.processes.delete(process_id)


@router.get("/processes/{process_id}/history")
def process_history(process_id: str, request: Request) -> list[dict]:
    auth = _auth(request)
    _process_for_auth(process_id, auth)
    return service.processes.history(process_id)


@router.get("/processes/{process_id}/versions/{version}")
def get_process_version(process_id: str, version: str, request: Request) -> dict:
    auth = _auth(request)
    doc = service.processes.get_version(process_id, version)
    if doc is None or doc.org_id != auth.org_id:
        raise HTTPException(status_code=404, detail="Version not found")
    return doc.to_dict()


@router.get("/processes/{process_id}/completeness")
def process_completeness(process_id: str, request: Request) -> dict:
    auth = _auth(request)
    doc = _process_for_auth(process_id, auth)
    return service.processes.completeness_breakdown(doc)


@router.get("/processes/{process_id}/diagram")
def process_diagram(process_id: str, request: Request) -> dict:
    """Return a Mermaid flowchart for this process.

    Uses the stored mermaid_flowchart if it exists; otherwise auto-generates
    one from the structured steps and decision_points.
    Returns: {mermaid: str, source: "stored"|"generated"|"none"}
    """
    try:
        auth = _auth(request)
        _process_for_auth(process_id, auth)
        return service.processes.generate_mermaid(process_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Process not found")


@router.post("/processes/{process_id}/runs", status_code=201)
def start_process_execution(process_id: str, request: Request, actor: str = "user") -> dict:
    """Start a new execution run for a process. Returns the run record."""
    try:
        auth = _auth(request)
        _process_for_auth(process_id, auth)
        return service.processes.start_execution(process_id, actor=auth.user_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Process not found")


@router.get("/processes/{process_id}/runs")
def list_process_executions(process_id: str, request: Request) -> list[dict]:
    """List all execution runs for a process, newest first."""
    auth = _auth(request)
    _process_for_auth(process_id, auth)
    return service.processes.list_executions(process_id)


@router.post("/processes/runs/{run_id}/advance")
def advance_process_step(run_id: str, request: Request) -> dict:
    """Advance an in-progress execution run to the next step."""
    try:
        auth = _auth(request)
        _run_for_auth(run_id, auth)
        return service.processes.advance_step(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Execution run not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/processes/runs/{run_id}/complete")
def complete_process_execution(run_id: str, request: Request) -> dict:
    """Mark an execution run as completed."""
    try:
        auth = _auth(request)
        _run_for_auth(run_id, auth)
        return service.processes.complete_execution(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Execution run not found")


@router.get("/processes/{process_id}/export")
def export_process(process_id: str, request: Request, format: str = "docx", org_id: str = "org-1") -> dict:
    """Export a process as a branded document. Returns {download_url, file_id, filename}."""
    auth = _auth(request)
    if service.docgen is None:
        raise HTTPException(status_code=501, detail="Document generation not available.")
    from packages.docgen.generators.base import DocumentContent, DocumentSection

    proc = _process_for_auth(process_id, auth)

    brand = service.brand.get_brand_or_default(auth.org_id).to_dict()
    sections: list[DocumentSection] = []

    # Overview
    overview_lines = [
        f"**Status:** {proc.status}",
        f"**Version:** {proc.version}",
        f"**Completeness:** {round(proc.completeness_score * 100)}%",
        f"**Trigger:** {proc.trigger}",
    ]
    if proc.roles:
        overview_lines.append(f"**Roles:** {', '.join(proc.roles)}")
    sections.append(DocumentSection(heading="Overview", body="\n".join(overview_lines), level=1))

    # Steps table
    if proc.steps:
        steps_table: list[list[str]] = [["#", "Step", "Owner", "SLA"]]
        for i, step in enumerate(proc.steps, 1):
            if isinstance(step, dict):
                name = step.get("name") or step.get("title", "—")
                owner = step.get("owner", "—")
                sla = step.get("sla", "—")
            else:
                name = getattr(step, "name", str(step))
                owner = getattr(step, "owner", "—")
                sla = getattr(step, "sla", "—")
            steps_table.append([str(i), name, owner, sla])
        sections.append(DocumentSection(heading="Steps", body="", level=1, table=steps_table))

    # Exceptions
    if proc.exceptions:
        exc_lines = []
        for exc in proc.exceptions:
            if isinstance(exc, dict):
                trigger = exc.get("trigger", "")
                handler = exc.get("handler", "")
                exc_lines.append(f"- **{trigger}:** {handler}")
        if exc_lines:
            sections.append(DocumentSection(heading="Exceptions & Edge Cases", body="\n".join(exc_lines), level=1))

    # Version history
    try:
        history = service.processes.get_history(process_id)
        if history:
            hist_table: list[list[str]] = [["Version", "Date", "Author", "Changes"]]
            for entry in history[:10]:  # cap at 10 rows
                if isinstance(entry, dict):
                    hist_table.append([
                        str(entry.get("version", "")),
                        str(entry.get("date", "")),
                        str(entry.get("author", "")),
                        str(entry.get("changes", "")),
                    ])
            if len(hist_table) > 1:
                sections.append(DocumentSection(heading="Version History", body="", level=1, table=hist_table))
    except Exception:
        pass

    doc_type = "deck" if format == "pptx" else "sop"
    content = DocumentContent(
        title=proc.process_name,
        document_type=doc_type,
        sections=sections,
        metadata={"author": brand.get("company_name", ""), "org_id": auth.org_id},
    )
    stored = service.docgen.generate(
        content, format=format, brand=brand, org_id=auth.org_id, created_by="friday-export"
    )
    return {"file_id": stored.file_id, "filename": stored.filename, "download_url": f"/files/{stored.file_id}"}
