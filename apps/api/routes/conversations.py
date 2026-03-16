from __future__ import annotations

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


class ConversationCreate(BaseModel):
    org_id: str = "org-1"
    workspace_id: Optional[str] = None
    title: str = "New conversation"
    thread_id: Optional[str] = None


class ConversationRename(BaseModel):
    title: str


class BranchPayload(BaseModel):
    at_message_id: str
    label: Optional[str] = None
    org_id: str = "org-1"


@router.get("/conversations")
def list_conversations(org_id: str = "org-1") -> list[dict]:
    return [t.to_dict() for t in service.conversations.list_threads(org_id=org_id)]


@router.post("/conversations", status_code=201)
def create_conversation(payload: ConversationCreate) -> dict:
    thread = service.conversations.create_thread(
        org_id=payload.org_id,
        workspace_id=payload.workspace_id,
        title=payload.title,
        thread_id=payload.thread_id,
    )
    return thread.to_dict()


@router.get("/conversations/{thread_id}/messages")
def get_conversation_messages(thread_id: str) -> list[dict]:
    messages = service.conversations.get_messages(thread_id)
    return [m.to_dict() for m in messages]


@router.patch("/conversations/{thread_id}")
def rename_conversation(thread_id: str, payload: ConversationRename) -> dict:
    thread = service.conversations.rename_thread(thread_id, payload.title)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread.to_dict()


@router.delete("/conversations/{thread_id}", status_code=204)
def delete_conversation(thread_id: str) -> None:
    service.conversations.delete_thread(thread_id)
    try:
        service.memory.clear_conversation(thread_id)
    except Exception:
        pass


@router.post("/conversations/{thread_id}/branch", status_code=201)
def branch_conversation(thread_id: str, payload: BranchPayload) -> dict:
    """Fork a thread at a specific message, returning the new branch thread."""
    try:
        branch = service.conversations.branch_thread(
            parent_thread_id=thread_id,
            at_message_id=payload.at_message_id,
            org_id=payload.org_id,
            label=payload.label,
        )
        return branch.to_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/conversations/{thread_id}/branches")
def get_conversation_branches(thread_id: str) -> list[dict]:
    """List all branch threads forked from the given thread."""
    branches = service.conversations.get_branches(thread_id)
    return [b.to_dict() for b in branches]
