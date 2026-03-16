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


class WorkspaceCreate(BaseModel):
    name: str
    description: str = ""
    icon: str = "🗂️"
    color: str = "#6366f1"
    type: str = "team"
    owner: str = "user"
    org_id: str = "default"
    visibility: str = "open"
    default_view: str = "chat"


class WorkspaceMemberAdd(BaseModel):
    user_id: str
    role: str = "editor"


class WorkspaceLinkCreate(BaseModel):
    entity_type: str
    entity_id: str


class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    color: str = "#6366f1"
    icon: str = "📁"


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None


@router.get("/workspaces")
def list_workspaces(org_id: str = "default") -> list[dict]:
    workspaces = service.workspaces.list(org_id=org_id)
    return [asdict(w) for w in workspaces]


@router.post("/workspaces", status_code=201)
def create_workspace(payload: WorkspaceCreate) -> dict:
    ws = service.workspaces.create(
        name=payload.name,
        org_id=payload.org_id,
        owner=payload.owner,
        type=payload.type,
        description=payload.description,
        icon=payload.icon,
        color=payload.color,
        visibility=payload.visibility,
        default_view=payload.default_view,
    )
    return asdict(ws)


@router.get("/workspaces/{workspace_id}")
def get_workspace(workspace_id: str) -> dict:
    ws = service.workspaces.get(workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="Not found")
    return asdict(ws)


@router.put("/workspaces/{workspace_id}")
def update_workspace(workspace_id: str, payload: dict) -> dict:
    ws = service.workspaces.update(workspace_id, **payload)
    if ws is None:
        raise HTTPException(status_code=404, detail="Not found")
    return asdict(ws)


@router.post("/workspaces/{workspace_id}/archive")
def archive_workspace(workspace_id: str) -> dict:
    service.workspaces.archive(workspace_id)
    return {"status": "archived", "workspace_id": workspace_id}


@router.delete("/workspaces/{workspace_id}", status_code=204)
def delete_workspace(workspace_id: str) -> None:
    """Delete (archive) a workspace. Admin-only by convention; enforced in the frontend."""
    service.workspaces.archive(workspace_id)


@router.get("/workspaces/{workspace_id}/members")
def list_workspace_members(workspace_id: str) -> list[dict]:
    members = service.workspaces.list_members(workspace_id)
    return [asdict(m) for m in members]


@router.post("/workspaces/{workspace_id}/members", status_code=201)
def add_workspace_member(workspace_id: str, payload: WorkspaceMemberAdd) -> dict:
    member = service.workspaces.add_member(workspace_id, user_id=payload.user_id, role=payload.role)
    return asdict(member)


@router.delete("/workspaces/{workspace_id}/members/{user_id}", status_code=204)
def remove_workspace_member(workspace_id: str, user_id: str) -> None:
    service.workspaces.remove_member(workspace_id, user_id)


@router.post("/workspaces/{workspace_id}/link", status_code=201)
def link_workspace_entity(workspace_id: str, payload: WorkspaceLinkCreate) -> dict:
    link = service.workspaces.link_entity(workspace_id, entity_type=payload.entity_type, entity_id=payload.entity_id)
    return asdict(link)


@router.get("/workspaces/{workspace_id}/overview")
def workspace_overview(workspace_id: str) -> dict:
    ws = service.workspaces.get(workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="Not found")
    members = service.workspaces.list_members(workspace_id)
    return {
        "workspace": asdict(ws),
        "member_count": len(members),
        "recent_okrs": [],
    }


@router.get("/workspaces/{workspace_id}/projects")
def list_projects(workspace_id: str) -> list[dict]:
    return [p.to_dict() for p in service.projects.list(workspace_id)]


@router.post("/workspaces/{workspace_id}/projects", status_code=201)
def create_project(workspace_id: str, payload: ProjectCreate) -> dict:
    project = service.projects.create(
        workspace_id=workspace_id,
        name=payload.name,
        description=payload.description,
        color=payload.color,
        icon=payload.icon,
    )
    return project.to_dict()


@router.put("/projects/{project_id}")
def update_project(project_id: str, payload: ProjectUpdate) -> dict:
    project = service.projects.update(project_id, **payload.model_dump(exclude_none=True))
    if project is None:
        raise HTTPException(status_code=404, detail="Not found")
    return project.to_dict()


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str) -> None:
    service.projects.delete(project_id)
