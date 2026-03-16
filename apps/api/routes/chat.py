from __future__ import annotations

import json as _json
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from apps.api.deps import service, upload_store
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
    # Optional context IDs from POST /upload — injected as context blocks
    context_ids: list[str] = []
    # Optional workspace context — injected into planning message when set
    workspace_id: Optional[str] = None


@router.post("/chat")
def chat(payload: ChatPayload, request: Request) -> dict:
    # PR-01: identity comes from auth context, not caller-supplied payload fields.
    auth = _auth(request)
    chat_data = payload.model_dump()
    chat_data["user_id"] = auth.user_id
    chat_data["org_id"] = auth.org_id
    try:
        result = service.execute_chat_payload(chat_data, upload_store=upload_store)
        # Persist conversation messages
        try:
            msg = payload.message.strip()
            if msg:
                service.conversations.add_message(
                    thread_id=payload.conversation_id,
                    role="user",
                    content=msg,
                    metadata={"org_id": auth.org_id, "workspace_id": payload.workspace_id},
                )
                friday_text = str((result.get("final_answer") or {}).get("direct_answer") or result.get("response") or "")
                if friday_text:
                    meta: dict = {"org_id": auth.org_id}
                    if result.get("run_id"): meta["run_id"] = result["run_id"]
                    if result.get("write_actions"): meta["write_actions"] = result["write_actions"]
                    service.conversations.add_message(
                        thread_id=payload.conversation_id,
                        role="friday",
                        content=friday_text,
                        metadata=meta,
                    )
        except Exception:
            pass  # best-effort
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/chat/stream")
def chat_stream(payload: ChatPayload, request: Request):
    """Server-sent events endpoint that streams synthesis tokens as they arrive from the LLM.

    SSE event types:
      event: status  — pipeline stage label
      event: token   — one synthesis token chunk
      event: done    — final metadata JSON
      event: error   — error message
    """
    from packages.common.models import ChatRequest

    # PR-01: identity from auth context, not payload.
    auth = _auth(request)

    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    request = ChatRequest(
        user_id=auth.user_id,
        org_id=auth.org_id,
        conversation_id=payload.conversation_id,
        message=message,
        context_packet=payload.context_packet,
        workspace_id=payload.workspace_id,
    )

    def _event_generator():
        full_text_parts: list[str] = []
        done_evt: dict | None = None
        for evt in service.manager.run_streaming(request):
            event_type = evt.get("event", "message")
            if event_type == "token":
                full_text_parts.append(evt.get("text", ""))
            if event_type == "done":
                done_evt = evt
                # Attempt doc generation if this was a full_deliverable request
                if evt.get("output_format") == "full_deliverable" and service.docgen is not None:
                    full_text = "".join(full_text_parts)
                    response_stub = {
                        "planner": {"output_format": "full_deliverable", "problem_statement": message},
                        "final_answer": {"direct_answer": full_text, "artifacts": {}},
                    }
                    service._maybe_generate_document(message, auth.org_id, response_stub)
                    if response_stub.get("generated_document"):
                        evt = {**evt, "generated_document": response_stub["generated_document"]}
                        done_evt = evt
            yield f"event: {event_type}\ndata: {_json.dumps(evt)}\n\n"
        # Persist conversation messages after streaming completes
        if full_text_parts:
            try:
                service.conversations.add_message(
                    thread_id=payload.conversation_id,
                    role="user",
                    content=message,
                    metadata={"org_id": auth.org_id, "workspace_id": payload.workspace_id},
                )
                friday_text = "".join(full_text_parts)
                meta: dict = {"org_id": auth.org_id}
                if done_evt:
                    if done_evt.get("run_id"): meta["run_id"] = done_evt["run_id"]
                    if done_evt.get("write_actions"): meta["write_actions"] = done_evt["write_actions"]
                service.conversations.add_message(
                    thread_id=payload.conversation_id,
                    role="friday",
                    content=friday_text,
                    metadata=meta,
                )
            except Exception:
                pass  # persistence is best-effort — never break the stream

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
