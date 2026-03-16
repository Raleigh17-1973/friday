from __future__ import annotations

from dataclasses import asdict
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from apps.api.deps import service
from apps.api.security import AuthContext

router = APIRouter()


def _auth(request: Request) -> AuthContext:
    return getattr(request.state, "auth", None) or AuthContext(
        user_id="user-1", org_id="org-1", roles=["user"]
    )


class ChatPayload(BaseModel):
    message: str
    user_id: str = "user-1"
    org_id: str = "org-1"
    conversation_id: str = "conv-1"
    context_packet: dict[str, Any] = {}
    context_ids: list[str] = []
    workspace_id: Optional[str] = None


class FeedbackPayload(BaseModel):
    approved: bool
    notes: str = ""


class CodeRunPayload(BaseModel):
    code: str
    data_files: dict[str, str] = {}
    org_id: str = "org-1"


@router.post("/runs")
def create_run(payload: ChatPayload) -> dict:
    from apps.api.routes.chat import chat

    def _execute(run_payload: dict) -> dict:
        return chat(ChatPayload(**run_payload))

    record = service.workflow.run(payload.model_dump(), _execute)
    return {
        "workflow_id": record.workflow_id,
        "status": record.status,
        "result": record.result,
    }


@router.get("/runs/{run_id}")
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


@router.post("/runs/{run_id}/feedback")
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


@router.post("/analysis/run")
def run_code(payload: CodeRunPayload) -> dict:
    return service.interpreter.run(payload.code, data_files=payload.data_files, org_id=payload.org_id)
