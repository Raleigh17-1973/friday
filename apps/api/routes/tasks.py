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


class TaskCreate(BaseModel):
    title: str
    description: str = ""
    assignee: Optional[str] = None
    due_date: Optional[str] = None
    priority: str = "medium"
    status: str = "open"
    workspace_id: Optional[str] = None
    okr_id: Optional[str] = None
    kr_id: Optional[str] = None
    process_id: Optional[str] = None
    initiative_id: Optional[str] = None
    created_by: str = "system"


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assignee: Optional[str] = None
    due_date: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    workspace_id: Optional[str] = None
    okr_id: Optional[str] = None
    kr_id: Optional[str] = None
    process_id: Optional[str] = None
    initiative_id: Optional[str] = None


class NotificationCreate(BaseModel):
    recipient_id: str
    title: str
    body: str = ""
    type: str = "general"
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None


@router.get("/tasks")
def list_tasks(
    assignee: Optional[str] = None,
    workspace_id: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    due_before: Optional[str] = None,
    okr_id: Optional[str] = None,
    limit: int = 200,
) -> list[dict]:
    tasks = service.tasks.list(
        assignee=assignee,
        workspace_id=workspace_id,
        status=status,
        priority=priority,
        due_before=due_before,
        okr_id=okr_id,
        limit=limit,
    )
    return [t.to_dict() for t in tasks]


@router.post("/tasks", status_code=201)
def create_task(payload: TaskCreate) -> dict:
    task = service.tasks.create(
        title=payload.title,
        description=payload.description,
        assignee=payload.assignee,
        due_date=payload.due_date,
        priority=payload.priority,
        status=payload.status,
        workspace_id=payload.workspace_id,
        okr_id=payload.okr_id,
        kr_id=payload.kr_id,
        process_id=payload.process_id,
        initiative_id=payload.initiative_id,
        created_by=payload.created_by,
    )
    # Notify assignee when task is assigned to someone
    if task.assignee:
        try:
            service.notifications.create(
                recipient_id=task.assignee,
                title=f"Task assigned: {task.title}",
                body=f"Priority: {task.priority}" + (f" · Due {task.due_date}" if task.due_date else ""),
                type="task_assigned",
                entity_type="task",
                entity_id=task.task_id,
            )
        except Exception:
            pass
    # Log to activity feed
    try:
        service.activity.log(
            action="task.created",
            entity_type="task",
            entity_id=task.task_id,
            entity_title=task.title,
            actor_id=payload.created_by or "system",
            assignee=task.assignee or "",
            priority=task.priority,
        )
    except Exception:
        pass
    return task.to_dict()


@router.get("/tasks/overdue")
def list_overdue_tasks() -> list[dict]:
    return [t.to_dict() for t in service.tasks.overdue()]


@router.get("/tasks/due-soon")
def list_due_soon_tasks(days: int = 7) -> list[dict]:
    return [t.to_dict() for t in service.tasks.due_soon(days=days)]


@router.get("/tasks/{task_id}")
def get_task(task_id: str) -> dict:
    task = service.tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task.to_dict()


@router.put("/tasks/{task_id}")
def update_task(task_id: str, payload: TaskUpdate) -> dict:
    changes = {k: v for k, v in payload.model_dump().items() if v is not None}
    task = service.tasks.update(task_id, **changes)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    # Log status transitions to activity feed
    try:
        action = "task.completed" if task.status == "done" else "task.updated"
        service.activity.log(
            action=action,
            entity_type="task",
            entity_id=task.task_id,
            entity_title=task.title,
            status=task.status,
        )
    except Exception:
        pass
    return task.to_dict()


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: str) -> None:
    if not service.tasks.delete(task_id):
        raise HTTPException(status_code=404, detail="Task not found")


@router.get("/notifications")
def list_notifications(
    request: Request,
    recipient_id: str = "user-1",
    unread_only: bool = False,
    limit: int = 50,
) -> list[dict]:
    auth = _auth(request)
    return [
        n.to_dict()
        for n in service.notifications.list(recipient_id=auth.user_id, unread_only=unread_only, limit=limit)
    ]


@router.get("/notifications/unread-count")
def unread_notification_count(request: Request, recipient_id: str = "user-1") -> dict:
    auth = _auth(request)
    return {"count": service.notifications.count_unread(auth.user_id)}


@router.post("/notifications", status_code=201)
def create_notification(payload: NotificationCreate) -> dict:
    notif = service.notifications.create(
        recipient_id=payload.recipient_id,
        title=payload.title,
        body=payload.body,
        type=payload.type,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
    )
    return notif.to_dict()


@router.post("/notifications/{notification_id}/read", status_code=204)
def mark_notification_read(notification_id: str, request: Request) -> None:
    auth = _auth(request)
    notification = service.notifications.get(notification_id)
    if notification is None or notification.recipient_id != auth.user_id:
        raise HTTPException(status_code=404, detail="Notification not found")
    service.notifications.mark_read(notification_id)


@router.post("/notifications/read-all", status_code=204)
def mark_all_notifications_read(request: Request, recipient_id: str = "user-1") -> None:
    auth = _auth(request)
    service.notifications.mark_all_read(auth.user_id)


@router.delete("/notifications/{notification_id}", status_code=204)
def delete_notification(notification_id: str, request: Request) -> None:
    auth = _auth(request)
    notification = service.notifications.get(notification_id)
    if notification is None or notification.recipient_id != auth.user_id:
        raise HTTPException(status_code=404, detail="Notification not found")
    service.notifications.delete(notification_id)


@router.get("/activity")
def list_activity(
    request: Request,
    org_id: str = "org-1",
    entity_type: Optional[str] = None,
    action_prefix: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    auth = _auth(request)
    entries = service.activity.list_for_org(
        org_id=auth.org_id,
        limit=limit,
        entity_type=entity_type,
        action_prefix=action_prefix,
    )
    return [e.to_dict() for e in entries]


@router.get("/activity/{entity_type}/{entity_id}")
def list_activity_for_entity(
    request: Request,
    entity_type: str,
    entity_id: str,
    limit: int = 50,
) -> list[dict]:
    auth = _auth(request)
    entries = service.activity.list_for_entity(
        org_id=auth.org_id,
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit,
    )
    return [e.to_dict() for e in entries]
