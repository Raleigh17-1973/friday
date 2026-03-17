from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from apps.api.deps import service
from apps.api.security import AuthContext

router = APIRouter()


def _auth(request: Request) -> AuthContext:
    return getattr(request.state, "auth", None) or AuthContext(
        user_id="user-1", org_id="org-1", roles=["user"]
    )


class BulkDecidePayload(BaseModel):
    approval_ids: list[str]
    decision: str   # "approve" | "reject"


class PromoteCandidatePayload(BaseModel):
    candidate_id: str
    approved: bool = False


def _approval_for_auth(approval_id: str, auth: AuthContext):
    try:
        req = service.approvals.get(approval_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="approval not found") from exc
    trace = service.audit.get_run(req.run_id)
    if trace is None or trace.org_id != auth.org_id:
        raise HTTPException(status_code=404, detail="approval not found")
    return req


def _candidate_for_auth(candidate_id: str, auth: AuthContext) -> dict:
    candidate = service.memory.get_candidate(candidate_id)
    if candidate is None or str(candidate.get("org_id")) != auth.org_id:
        raise HTTPException(status_code=404, detail="candidate not found")
    return candidate


@router.post("/approvals/{approval_id}/approve")
def approve(approval_id: str, request: Request) -> dict:
    auth = _auth(request)
    req = _approval_for_auth(approval_id, auth)
    req = service.approvals.approve(approval_id)
    try:
        service.activity.log(
            action="generic", entity_type="approval", entity_id=approval_id,
            entity_title=req.action_summary[:80], actor_id=auth.user_id, decision="approved",
        )
    except Exception:
        pass
    return asdict(req)


@router.post("/approvals/{approval_id}/execute")
def execute_approval(approval_id: str, request: Request) -> dict:
    """PR-08: Execute the deferred write plan for an already-approved ApprovalRequest.

    Call this after POST /approvals/{id}/approve to run the tool actions that were
    held pending human sign-off.
    """
    auth = _auth(request)
    _approval_for_auth(approval_id, auth)
    try:
        write_actions = service.manager.execute_pending_write_plan(approval_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"approval_id": approval_id, "write_actions": write_actions, "count": len(write_actions)}


@router.post("/approvals/{approval_id}/reject")
def reject(approval_id: str, request: Request) -> dict:
    auth = _auth(request)
    req = _approval_for_auth(approval_id, auth)
    req = service.approvals.reject(approval_id)
    try:
        service.activity.log(
            action="generic", entity_type="approval", entity_id=approval_id,
            entity_title=req.action_summary[:80], actor_id=auth.user_id, decision="rejected",
        )
    except Exception:
        pass
    return asdict(req)


@router.get("/approvals/{approval_id}")
def get_approval(approval_id: str, request: Request) -> dict:
    auth = _auth(request)
    req = _approval_for_auth(approval_id, auth)
    return asdict(req)


@router.post("/approvals/bulk-decide", status_code=200)
def bulk_decide(payload: BulkDecidePayload, request: Request) -> dict:
    auth = _auth(request)
    if payload.decision not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="decision must be 'approve' or 'reject'")
    results: list[dict] = []
    for aid in payload.approval_ids:
        try:
            req = _approval_for_auth(aid, auth)
            req = service.approvals.approve(aid) if payload.decision == "approve" else service.approvals.reject(aid)
            results.append({"approval_id": aid, "status": req.status})
            try:
                service.activity.log(
                    action="generic", entity_type="approval", entity_id=aid,
                    entity_title=req.action_summary[:80], actor_id=auth.user_id,
                    decision=payload.decision + "d", bulk=True,
                )
            except Exception:
                pass
        except HTTPException:
            results.append({"approval_id": aid, "error": "not found"})
        except KeyError:
            results.append({"approval_id": aid, "error": "not found"})
    return {"processed": len(results), "results": results}


@router.post("/approvals/{approval_id}/assign")
def assign_approval(approval_id: str, payload: dict, request: Request) -> dict:
    """Phase 9: Assign a reviewer to an approval request."""
    auth = _auth(request)
    assignee = str(payload.get("assignee", ""))
    if not assignee:
        raise HTTPException(status_code=400, detail="assignee is required")
    _approval_for_auth(approval_id, auth)
    req = service.approvals.assign(approval_id, assignee)
    try:
        service.notifications.create(
            recipient_id=assignee,
            type="approval_required",
            title="Approval assigned to you",
            body=req.action_summary[:200],
            entity_type="approval",
            entity_id=approval_id,
        )
    except Exception:
        pass
    return asdict(req)


@router.get("/approvals")
def list_approvals(request: Request, status: str = "pending", assignee: Optional[str] = None) -> dict:
    auth = _auth(request)
    if assignee:
        items = service.approvals.list_for_assignee(assignee)
    elif status == "all":
        items = service.approvals.list_all()
    else:
        items = service.approvals.list_pending()
    filtered = []
    for item in items:
        trace = service.audit.get_run(item.run_id)
        if trace is not None and trace.org_id == auth.org_id:
            filtered.append(item)
    return {"approvals": [asdict(r) for r in filtered]}


@router.get("/memories")
def list_memories(
    request: Request,
    org_id: str = "org-1",
    workspace_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """Return semantic memories with metadata. Supports workspace_id filtering and pagination."""
    auth = _auth(request)
    entries = service.memory.list_semantic(
        auth.org_id, workspace_id=workspace_id, limit=limit, offset=offset
    )
    # Normalize value to string for display
    for e in entries:
        if not isinstance(e.get("value"), str):
            e["value"] = str(e["value"])
    return {"org_id": auth.org_id, "memories": entries, "count": len(entries)}


@router.delete("/memories/{org_id}/{key}")
def delete_memory(org_id: str, key: str, request: Request) -> dict:
    """Remove a single semantic memory entry from both in-memory and durable store."""
    auth = _auth(request)
    if org_id != auth.org_id:
        raise HTTPException(status_code=404, detail="memory not found")
    # Remove from in-memory store
    store = service.memory._semantic_by_org.get(auth.org_id, {})
    store.pop(key, None)
    # Remove from SQLite if repository is present
    if service.memory._repository is not None:
        try:
            with service.memory._repository._connect() as conn:
                conn.execute(
                    "DELETE FROM semantic_memories WHERE org_id = ? AND memory_key = ?",
                    (auth.org_id, key),
                )
        except Exception:
            pass
    return {"deleted": key}


@router.get("/memories/search")
def search_memories(request: Request, org_id: str, q: str) -> dict:
    auth = _auth(request)
    if org_id != auth.org_id:
        raise HTTPException(status_code=404, detail="memory not found")
    return service.memory.search(org_id=auth.org_id, query=q)


@router.get("/memories/candidates")
def list_memory_candidates(request: Request, org_id: str = "org-1") -> dict:
    """Return unreviewed memory candidates pending approval."""
    auth = _auth(request)
    candidates = service.memory.list_candidates(auth.org_id)
    return {"org_id": auth.org_id, "candidates": candidates, "count": len(candidates)}


@router.post("/memories/candidates/promote")
def promote_memory_candidate(payload: PromoteCandidatePayload, request: Request) -> dict:
    auth = _auth(request)
    _candidate_for_auth(payload.candidate_id, auth)
    try:
        return service.memory.promote_candidate(payload.candidate_id, approved=payload.approved)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="candidate not found") from exc
