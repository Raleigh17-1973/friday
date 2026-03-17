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


def _workspace_for_auth(workspace_id: str, request: Request):
    auth = _auth(request)
    ws = service.workspaces.get_for_org(workspace_id, auth.org_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="Not found")
    return ws


def _project_for_auth(project_id: str, request: Request):
    project = service.projects.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Not found")
    _workspace_for_auth(project.workspace_id, request)
    return project


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
def list_workspaces(request: Request, org_id: str = "default") -> list[dict]:
    auth = _auth(request)
    workspaces = service.workspaces.list(org_id=auth.org_id)
    return [asdict(w) for w in workspaces]


@router.post("/workspaces", status_code=201)
def create_workspace(payload: WorkspaceCreate, request: Request) -> dict:
    auth = _auth(request)
    ws = service.workspaces.create(
        name=payload.name,
        org_id=auth.org_id,
        owner=auth.user_id,
        type=payload.type,
        description=payload.description,
        icon=payload.icon,
        color=payload.color,
        visibility=payload.visibility,
        default_view=payload.default_view,
    )
    return asdict(ws)


@router.get("/workspaces/{workspace_id}")
def get_workspace(workspace_id: str, request: Request) -> dict:
    ws = _workspace_for_auth(workspace_id, request)
    return asdict(ws)


@router.put("/workspaces/{workspace_id}")
def update_workspace(workspace_id: str, payload: dict, request: Request) -> dict:
    auth = _auth(request)
    ws = service.workspaces.update_for_org(workspace_id, auth.org_id, **payload)
    if ws is None:
        raise HTTPException(status_code=404, detail="Not found")
    return asdict(ws)


@router.post("/workspaces/{workspace_id}/archive")
def archive_workspace(workspace_id: str, request: Request) -> dict:
    auth = _auth(request)
    if not service.workspaces.archive_for_org(workspace_id, auth.org_id):
        raise HTTPException(status_code=404, detail="Not found")
    return {"status": "archived", "workspace_id": workspace_id}


@router.delete("/workspaces/{workspace_id}", status_code=204)
def delete_workspace(workspace_id: str, request: Request) -> None:
    """Delete (archive) a workspace. Admin-only by convention; enforced in the frontend."""
    auth = _auth(request)
    if not service.workspaces.archive_for_org(workspace_id, auth.org_id):
        raise HTTPException(status_code=404, detail="Not found")


@router.get("/workspaces/{workspace_id}/members")
def list_workspace_members(workspace_id: str, request: Request) -> list[dict]:
    auth = _auth(request)
    members = service.workspaces.list_members_for_org(workspace_id, auth.org_id)
    if not members and service.workspaces.get_for_org(workspace_id, auth.org_id) is None:
        raise HTTPException(status_code=404, detail="Not found")
    return [asdict(m) for m in members]


@router.post("/workspaces/{workspace_id}/members", status_code=201)
def add_workspace_member(workspace_id: str, payload: WorkspaceMemberAdd, request: Request) -> dict:
    auth = _auth(request)
    member = service.workspaces.add_member_for_org(workspace_id, auth.org_id, user_id=payload.user_id, role=payload.role)
    if member is None:
        raise HTTPException(status_code=404, detail="Not found")
    return asdict(member)


@router.delete("/workspaces/{workspace_id}/members/{user_id}", status_code=204)
def remove_workspace_member(workspace_id: str, user_id: str, request: Request) -> None:
    auth = _auth(request)
    if not service.workspaces.remove_member_for_org(workspace_id, auth.org_id, user_id):
        raise HTTPException(status_code=404, detail="Not found")


@router.post("/workspaces/{workspace_id}/link", status_code=201)
def link_workspace_entity(workspace_id: str, payload: WorkspaceLinkCreate, request: Request) -> dict:
    auth = _auth(request)
    link = service.workspaces.link_entity_for_org(workspace_id, auth.org_id, entity_type=payload.entity_type, entity_id=payload.entity_id)
    if link is None:
        raise HTTPException(status_code=404, detail="Not found")
    return asdict(link)


@router.get("/workspaces/{workspace_id}/overview")
def workspace_overview(workspace_id: str, request: Request) -> dict:
    ws = _workspace_for_auth(workspace_id, request)
    members = service.workspaces.list_members(workspace_id)
    return {
        "workspace": asdict(ws),
        "member_count": len(members),
        "recent_okrs": [],
    }


@router.get("/workspaces/{workspace_id}/projects")
def list_projects(workspace_id: str, request: Request) -> list[dict]:
    _workspace_for_auth(workspace_id, request)
    return [p.to_dict() for p in service.projects.list(workspace_id)]


@router.post("/workspaces/{workspace_id}/projects", status_code=201)
def create_project(workspace_id: str, payload: ProjectCreate, request: Request) -> dict:
    _workspace_for_auth(workspace_id, request)
    project = service.projects.create(
        workspace_id=workspace_id,
        name=payload.name,
        description=payload.description,
        color=payload.color,
        icon=payload.icon,
    )
    return project.to_dict()


@router.put("/projects/{project_id}")
def update_project(project_id: str, payload: ProjectUpdate, request: Request) -> dict:
    project = _project_for_auth(project_id, request)
    project = service.projects.update_for_workspace(
        project_id,
        project.workspace_id,
        **payload.model_dump(exclude_none=True),
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Not found")
    return project.to_dict()


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str, request: Request) -> None:
    project = _project_for_auth(project_id, request)
    if not service.projects.delete_for_workspace(project_id, project.workspace_id):
        raise HTTPException(status_code=404, detail="Not found")
