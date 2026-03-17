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


class OrgProfilePayload(BaseModel):
    company_name: str
    industry: str = ""
    stage: str = "growth"
    fiscal_year_end: str = "12-31"
    headcount: int = 0
    founded_year: Optional[int] = None
    mission: str = ""
    values: list[str] = []
    org_id: str = "org-1"


class PersonPayload(BaseModel):
    name: str
    role: str
    department: str
    email: str = ""
    reports_to: str = ""
    org_id: str = "org-1"


class PriorityPayload(BaseModel):
    title: str
    description: str
    owner: str
    due_date: str
    tags: list[str] = []
    org_id: str = "org-1"


class MeetingCreatePayload(BaseModel):
    title: str
    scheduled_at: str
    attendees: list[str] = []
    agenda: list[str] = []
    duration_minutes: int = 60
    org_id: str = "org-1"


class MeetingNotesPayload(BaseModel):
    raw_text: str
    org_id: str = "org-1"


class DecisionPayload(BaseModel):
    title: str
    context: str
    rationale: str
    owner: str
    options_considered: list[str] = []
    tags: list[str] = []
    reversibility: str = "reversible"
    confidence: float = 0.8
    related_run_id: str = ""
    org_id: str = "org-1"


@router.get("/org/profile")
def get_org_profile(request: Request, org_id: str = "org-1") -> dict:
    auth = _auth(request)
    p = service.org_context.get_profile(auth.org_id)
    return asdict(p) if p else {}


@router.put("/org/profile")
def upsert_org_profile(payload: OrgProfilePayload, request: Request) -> dict:
    from packages.org_context import OrgProfile
    auth = _auth(request)
    profile = OrgProfile(
        org_id=auth.org_id, company_name=payload.company_name,
        industry=payload.industry, stage=payload.stage,
        fiscal_year_end=payload.fiscal_year_end, headcount=payload.headcount,
        founded_year=payload.founded_year, mission=payload.mission,
        values=payload.values)
    return asdict(service.org_context.upsert_profile(profile))


@router.get("/org/people")
def list_people(request: Request, org_id: str = "org-1", department: Optional[str] = None) -> list[dict]:
    auth = _auth(request)
    return [asdict(p) for p in service.org_context.list_people(auth.org_id, department)]


@router.post("/org/people", status_code=201)
def add_person(payload: PersonPayload, request: Request) -> dict:
    from packages.org_context import Person
    from uuid import uuid4
    auth = _auth(request)
    p = Person(person_id=f"person_{uuid4().hex[:12]}", name=payload.name,
                role=payload.role, department=payload.department,
                email=payload.email, reports_to=payload.reports_to, org_id=auth.org_id)
    return asdict(service.org_context.upsert_person(p))


@router.get("/org/chart")
def org_chart(request: Request, org_id: str = "org-1") -> dict:
    auth = _auth(request)
    return service.org_context.org_chart(auth.org_id)


@router.get("/org/priorities")
def list_priorities(request: Request, org_id: str = "org-1") -> list[dict]:
    auth = _auth(request)
    return [asdict(p) for p in service.org_context.list_priorities(auth.org_id)]


@router.post("/org/priorities", status_code=201)
def add_priority(payload: PriorityPayload, request: Request) -> dict:
    auth = _auth(request)
    return asdict(service.org_context.add_priority(
        title=payload.title, description=payload.description,
        owner=payload.owner, due_date=payload.due_date,
        org_id=auth.org_id, tags=payload.tags))


@router.get("/meetings")
def list_meetings(request: Request, org_id: str = "org-1", status: Optional[str] = None) -> list[dict]:
    auth = _auth(request)
    return [asdict(m) for m in service.meetings.list_meetings(org_id=auth.org_id, status=status)]


@router.post("/meetings", status_code=201)
def create_meeting(payload: MeetingCreatePayload, request: Request) -> dict:
    auth = _auth(request)
    m = service.meetings.create_meeting(
        title=payload.title, scheduled_at=payload.scheduled_at,
        attendees=payload.attendees, agenda=payload.agenda,
        duration_minutes=payload.duration_minutes, org_id=auth.org_id)
    return asdict(m)


@router.post("/meetings/{meeting_id}/notes", status_code=201)
def process_meeting_notes(meeting_id: str, payload: MeetingNotesPayload, request: Request) -> dict:
    auth = _auth(request)
    note = service.meetings.process_notes(meeting_id, payload.raw_text, org_id=auth.org_id)
    result = asdict(note)
    result["action_items"] = [asdict(a) for a in note.action_items]

    # Phase 4: Auto-create a Task for each action item so they appear in /tasks
    created_task_ids: list[str] = []
    for item in note.action_items:
        try:
            assignee = item.owner if item.owner and item.owner.upper() != "TBD" else None
            task = service.tasks.create(
                title=item.description[:200],
                description=f"Action item from meeting {meeting_id}",
                assignee=assignee,
                due_date=item.due_date or None,
                priority="medium",
                status="open",
                created_by="friday",
            )
            created_task_ids.append(task.task_id)
            if assignee:
                try:
                    service.notifications.create(
                        recipient_id=assignee,
                        type="task_assigned",
                        title="New task from meeting",
                        body=item.description[:200],
                        entity_type="task",
                        entity_id=task.task_id,
                    )
                except Exception:
                    pass
        except Exception:
            pass
    result["tasks_created"] = created_task_ids
    return result


@router.get("/meetings/action-items")
def list_action_items(
    request: Request,
    org_id: str = "org-1",
    status: str = "open",
    owner: Optional[str] = None,
) -> list[dict]:
    auth = _auth(request)
    return [asdict(a) for a in service.meetings.list_action_items(org_id=auth.org_id, status=status, owner=owner)]


@router.post("/meetings/action-items/{item_id}/complete")
def complete_action_item(item_id: str) -> dict:
    service.meetings.complete_action_item(item_id)
    return {"status": "done"}


@router.get("/decisions")
def list_decisions(request: Request, org_id: str = "org-1", tag: Optional[str] = None) -> list[dict]:
    auth = _auth(request)
    return [asdict(d) for d in service.decisions.list_decisions(auth.org_id, tag=tag)]


@router.post("/decisions", status_code=201)
def log_decision(payload: DecisionPayload, request: Request) -> dict:
    auth = _auth(request)
    return asdict(service.decisions.log(
        title=payload.title, context=payload.context, rationale=payload.rationale,
        owner=payload.owner, options_considered=payload.options_considered,
        org_id=auth.org_id, tags=payload.tags, reversibility=payload.reversibility,
        confidence=payload.confidence, related_run_id=payload.related_run_id))


@router.get("/decisions/search")
def search_decisions(request: Request, q: str, org_id: str = "org-1") -> list[dict]:
    auth = _auth(request)
    return [asdict(d) for d in service.decisions.search(q, auth.org_id)]


@router.post("/decisions/{decision_id}/outcome")
def record_decision_outcome(decision_id: str, outcome: str) -> dict:
    service.decisions.record_outcome(decision_id, outcome)
    return {"status": "recorded"}
