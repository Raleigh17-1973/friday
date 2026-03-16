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


class ObjectiveCreate(BaseModel):
    org_id: str = "default"
    workspace_id: Optional[str] = None
    title: str
    description: str = ""
    owner: str = "user"
    collaborators: list[str] = []
    parent_id: Optional[str] = None
    level: str = "team"
    period: str = "2026-Q1"
    status: str = "active"
    confidence: float = 0.7
    rationale: str = ""
    linked_initiatives: list[str] = []
    linked_docs: list[str] = []


class KeyResultCreate(BaseModel):
    title: str
    metric_type: str = "number"
    baseline: float = 0.0
    current_value: float = 0.0
    target_value: float = 100.0
    unit: str = ""
    owner: str = "user"
    data_source: str = ""
    update_cadence: str = "weekly"
    status: str = "active"
    confidence: float = 0.7
    due_date: str = ""
    notes: str = ""


class InitiativeCreate(BaseModel):
    title: str
    owner: str = "user"
    kr_id: Optional[str] = None
    status: str = "not_started"
    due_date: str = ""
    description: str = ""
    org_id: str = "default"
    workspace_id: Optional[str] = None


class CheckInCreate(BaseModel):
    author: str = "user"
    status: str = "on_track"
    confidence: float = 0.7
    highlights: str = ""
    blockers: str = ""
    next_steps: str = ""


class InitiativeUpdate(BaseModel):
    status: Optional[str] = None
    owner: Optional[str] = None
    title: Optional[str] = None
    due_date: Optional[str] = None
    description: Optional[str] = None


class KRProgressPayload(BaseModel):
    current: float


class LinkKPIPayload(BaseModel):
    kpi_id: Optional[str] = None   # None = unlink


class OKRGradePayload(BaseModel):
    grade: float  # 0.0 – 1.0
    retrospective: str = ""
    carry_forward: bool = False
    next_period: Optional[str] = None


class KPICreatePayload(BaseModel):
    name: str
    unit: str
    target_value: Optional[float] = None  # frontend uses target_value
    target: Optional[float] = None        # legacy alias
    direction: str = "higher_is_better"
    category: str = ""
    frequency: str = "monthly"
    data_source: str = "manual"
    org_id: str = "org-1"


class KPIDataPayload(BaseModel):
    value: float
    source: str = "manual"


def _normalize_kpi(raw: dict) -> dict:
    """Convert backend KPI shape → frontend KPI shape."""
    latest = raw.get("latest_value") or 0.0
    target = raw.get("target") or raw.get("target_value") or 0.0
    on_target = raw.get("on_target")
    direction = raw.get("direction", "higher_is_better")

    if latest is None or latest == 0.0 and target == 0.0:
        status = "at_risk"
    elif direction == "higher_is_better":
        pct = (latest / target) if target else 0
        status = "on_track" if pct >= 0.9 else ("at_risk" if pct >= 0.7 else "behind")
    else:
        pct = (latest / target) if target else 0
        status = "on_track" if pct <= 1.1 else ("at_risk" if pct <= 1.3 else "behind")

    return {
        "kpi_id": raw.get("kpi_id", ""),
        "name": raw.get("name", ""),
        "unit": raw.get("unit", ""),
        "current_value": latest if latest is not None else 0.0,
        "target_value": target,
        "direction": direction,
        "category": raw.get("category", ""),
        "status": status,
    }


@router.get("/okrs")
def list_okrs(
    org_id: str = "default",
    workspace_id: Optional[str] = None,
    level: Optional[str] = None,
    period: Optional[str] = None,
    status: Optional[str] = None,
) -> list[dict]:
    objs = service.okrs.list_objectives(
        org_id=org_id,
        workspace_id=workspace_id,
        parent_id=None,  # return all, not just root
        level=level,
        period=period,
        status=status,
    )
    return [asdict(o) for o in objs]


@router.post("/okrs", status_code=201)
def create_objective_full(payload: ObjectiveCreate) -> dict:
    obj = service.okrs.create_objective(
        title=payload.title,
        period=payload.period,
        org_id=payload.org_id,
        description=payload.description,
        owner=payload.owner,
        level=payload.level,
        parent_id=payload.parent_id,
        workspace_id=payload.workspace_id,
        collaborators=payload.collaborators,
        rationale=payload.rationale,
        confidence=payload.confidence,
    )
    return asdict(obj)


@router.get("/okrs/overdue-checkins")
def list_overdue_checkins(org_id: str = "org-1", days: int = 7) -> list[dict]:
    """Return active objectives with no check-in in the last `days` days."""
    objs = service.okrs.list_overdue_checkins(org_id=org_id, days=days)
    return [asdict(o) for o in objs]


@router.get("/okrs/{obj_id}")
def get_objective(obj_id: str) -> dict:
    result = service.okrs.get_objective_with_details(obj_id)
    if not result:
        raise HTTPException(status_code=404, detail="Not found")
    return result


@router.put("/okrs/{obj_id}")
def update_objective(obj_id: str, payload: dict) -> dict:
    obj = service.okrs.update_objective(obj_id, **payload)
    if obj is None:
        raise HTTPException(status_code=404, detail="Not found")
    return asdict(obj)


@router.delete("/okrs/{obj_id}", status_code=204)
def delete_objective(obj_id: str) -> None:
    service.okrs.update_objective(obj_id, status="cancelled")


@router.get("/okrs/{obj_id}/children")
def list_objective_children(obj_id: str, org_id: str = "org-1") -> list[dict]:
    children = service.okrs.get_children(obj_id, org_id=org_id)
    return [asdict(c) for c in children]


@router.post("/okrs/{obj_id}/key-results", status_code=201)
def create_key_result_full(obj_id: str, payload: KeyResultCreate) -> dict:
    obj = service.okrs.get_objective(obj_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Not found")
    kr = service.okrs.create_key_result(
        objective_id=obj_id,
        title=payload.title,
        target_value=payload.target_value,
        org_id=obj.org_id,
        unit=payload.unit,
        baseline=payload.baseline,
        owner=payload.owner,
        metric_type=payload.metric_type,
        data_source=payload.data_source,
        update_cadence=payload.update_cadence,
        due_date=payload.due_date,
        confidence=payload.confidence,
    )
    return asdict(kr)


@router.put("/okrs/key-results/{kr_id}")
def update_key_result_full(kr_id: str, payload: dict) -> dict:
    kr = service.okrs.update_key_result(kr_id, **payload)
    if kr is None:
        raise HTTPException(status_code=404, detail="Not found")
    return asdict(kr)


@router.post("/okrs/{obj_id}/initiatives", status_code=201)
def create_initiative(obj_id: str, payload: InitiativeCreate) -> dict:
    init = service.okrs.create_initiative(
        title=payload.title,
        objective_id=obj_id,
        org_id=payload.org_id,
        owner=payload.owner,
        kr_id=payload.kr_id,
        description=payload.description,
        due_date=payload.due_date,
        workspace_id=payload.workspace_id,
    )
    return asdict(init)


@router.post("/okrs/{obj_id}/check-in", status_code=201)
def okr_checkin(obj_id: str, payload: CheckInCreate) -> dict:
    obj = service.okrs.get_objective(obj_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Not found")
    checkin = service.okrs.add_checkin(
        objective_id=obj_id,
        notes="",
        confidence=payload.confidence,
        status=payload.status,
        author=payload.author,
        org_id=obj.org_id,
        highlights=payload.highlights,
        blockers=payload.blockers,
        next_steps=payload.next_steps,
    )
    # Log to activity feed
    try:
        service.activity.log(
            action="okr.checkin",
            entity_type="objective",
            entity_id=obj_id,
            entity_title=obj.title,
            actor_id=payload.author or "system",
            org_id=obj.org_id,
            status=payload.status,
            confidence=payload.confidence,
        )
    except Exception:
        pass
    return asdict(checkin)


@router.put("/okrs/initiatives/{initiative_id}", status_code=200)
def update_initiative(initiative_id: str, payload: InitiativeUpdate) -> dict:
    service.okrs.update_initiative(
        initiative_id,
        status=payload.status,
        owner=payload.owner,
        title=payload.title,
        due_date=payload.due_date,
        description=payload.description,
    )
    return {"ok": True}


@router.put("/okrs/key-results/{kr_id}/progress")
def update_kr_progress(kr_id: str, payload: KRProgressPayload) -> dict:
    return service.okrs.update_key_result_progress(kr_id, current=payload.current)


@router.post("/okrs/key-results/{kr_id}/link-kpi", status_code=200)
def link_kr_to_kpi(kr_id: str, payload: LinkKPIPayload) -> dict:
    """Associate a Key Result with a KPI for automatic value sync.
    Pass kpi_id=null to remove the link."""
    ok = service.okrs.link_kr_to_kpi(kr_id, payload.kpi_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Key result not found")
    # If linking (not unlinking), immediately sync the latest KPI value
    if payload.kpi_id:
        try:
            latest = service.kpis.get_latest_value(payload.kpi_id)
            if latest is not None:
                service.okrs.sync_kr_from_kpi_value(kr_id, latest)
        except Exception:
            pass
    return {"ok": True, "kr_id": kr_id, "kpi_id": payload.kpi_id}


@router.get("/okrs/{obj_id}/hierarchy")
def get_okr_hierarchy(obj_id: str) -> dict:
    """Return a full nested tree: objective + all descendant children + their KRs."""
    tree = service.okrs.get_hierarchy(obj_id)
    if not tree:
        raise HTTPException(status_code=404, detail="Objective not found")
    return tree


@router.post("/okrs/{obj_id}/grade", status_code=200)
def grade_objective(obj_id: str, payload: OKRGradePayload) -> dict:
    """Grade a completed objective on a 0.0–1.0 scale.

    Grade labels:
      0.0–0.09 = Did Not Start
      0.1–0.44 = Partial
      0.45–0.74 = Good Progress
      0.75–1.0  = Fully Achieved

    Set carry_forward=true to clone the objective into the next period.
    """
    try:
        result = service.okrs.grade_objective(
            obj_id,
            grade=payload.grade,
            retrospective=payload.retrospective,
            carry_forward=payload.carry_forward,
            next_period=payload.next_period,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Objective not found")
    # Log activity
    try:
        service.activity.log(
            action="graded", entity_type="objective", entity_id=obj_id,
            entity_title=result.get("title", obj_id), actor_id="user-1",
            grade=result["grade"], grade_label=result["grade_label"],
        )
    except Exception:
        pass
    return result


@router.get("/okrs/{obj_id}/export")
def export_okr(obj_id: str, format: str = "docx", org_id: str = "org-1") -> dict:
    """Export a full OKR hierarchy as a branded document. Returns {download_url, file_id, filename}."""
    if service.docgen is None:
        raise HTTPException(status_code=501, detail="Document generation not available.")
    from packages.docgen.generators.base import DocumentContent, DocumentSection

    obj = service.okrs.get_objective(obj_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Objective not found")

    brand = service.brand.get_brand_or_default(org_id).to_dict()
    krs = service.okrs.list_key_results(obj_id)
    initiatives = service.okrs.list_initiatives(obj_id)

    sections: list[DocumentSection] = []

    # Overview section
    overview_lines = [
        f"**Period:** {obj.period}",
        f"**Level:** {obj.level}",
        f"**Status:** {obj.status}",
        f"**Progress:** {round(obj.progress * 100)}%",
        f"**Confidence:** {round(obj.confidence_score * 100)}%",
    ]
    if obj.description:
        overview_lines.append(f"\n{obj.description}")
    sections.append(DocumentSection(heading="Overview", body="\n".join(overview_lines), level=1))

    # Key Results section
    if krs:
        kr_table: list[list[str]] = [["Key Result", "Target", "Current", "Progress", "Status"]]
        for kr in krs:
            pct = f"{round(kr.progress * 100)}%" if kr.progress is not None else "—"
            current = str(round(kr.current_value, 2)) if kr.current_value is not None else "—"
            target = f"{kr.target_value} {kr.unit}" if kr.unit else str(kr.target_value)
            kr_table.append([kr.title, target, current, pct, kr.status])
        sections.append(DocumentSection(
            heading="Key Results",
            body="",
            level=1,
            table=kr_table,
        ))

    # Initiatives section
    if initiatives:
        init_table: list[list[str]] = [["Initiative", "Owner", "Status", "Due Date"]]
        for ini in initiatives:
            init_table.append([ini.title, ini.owner or "—", ini.status, ini.due_date or "—"])
        sections.append(DocumentSection(
            heading="Initiatives",
            body="",
            level=1,
            table=init_table,
        ))

    # Child objectives (brief list)
    children = service.okrs.get_children(obj_id, org_id=obj.org_id)
    if children:
        child_body = "\n".join(f"- {c.title} ({round(c.progress * 100)}% · {c.status})" for c in children)
        sections.append(DocumentSection(heading="Aligned Objectives", body=child_body, level=1))

    doc_type = "deck" if format == "pptx" else "report"
    content = DocumentContent(
        title=obj.title,
        document_type=doc_type,
        sections=sections,
        metadata={"author": brand.get("company_name", ""), "org_id": org_id},
    )
    stored = service.docgen.generate(
        content, format=format, brand=brand, org_id=org_id, created_by="friday-export"
    )
    return {"file_id": stored.file_id, "filename": stored.filename, "download_url": f"/files/{stored.file_id}"}


@router.get("/kpis")
def list_kpis(org_id: str = "org-1") -> list[dict]:
    return [_normalize_kpi(k) for k in service.kpis.kpi_status(org_id=org_id)]


@router.post("/kpis", status_code=201)
def create_kpi(payload: KPICreatePayload) -> dict:
    target = payload.target_value if payload.target_value is not None else payload.target
    kpi = service.kpis.create_kpi(
        name=payload.name, unit=payload.unit, target=target,
        frequency=payload.frequency, data_source=payload.data_source, org_id=payload.org_id)
    return _normalize_kpi({
        **kpi.to_dict(),
        "latest_value": 0.0,
        "on_target": None,
        "direction": payload.direction,
        "category": payload.category,
    })


@router.post("/kpis/{kpi_id}/data", status_code=201)
def record_kpi_data(kpi_id: str, payload: KPIDataPayload) -> dict:
    dp = service.kpis.record_data_point(kpi_id, value=payload.value, source=payload.source)
    # Auto-sync any KRs linked to this KPI
    try:
        linked_krs = service.okrs.list_key_results_by_kpi(kpi_id)
        for kr in linked_krs:
            service.okrs.sync_kr_from_kpi_value(kr.kr_id, payload.value)
    except Exception:
        pass  # KPI sync is best-effort; never fail the data-record call
    return dp.to_dict()


@router.get("/kpis/{kpi_id}/trend")
def kpi_trend(kpi_id: str, limit: int = 30) -> list[dict]:
    return [dp.to_dict() for dp in service.kpis.get_trend(kpi_id, limit=limit)]
