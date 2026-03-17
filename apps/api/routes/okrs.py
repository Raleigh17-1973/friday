from __future__ import annotations

"""Enterprise OKR routes — replaces legacy flat OKR endpoints."""

from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from apps.api.deps import service
from apps.api.security import AuthContext

router = APIRouter(tags=["OKRs"])


def _auth(request: Request) -> AuthContext:
    return getattr(request.state, "auth", None) or AuthContext(
        user_id="user-1", org_id="org-1", roles=["user"]
    )


def _org_node_for_auth(node_id: str, auth: AuthContext):
    node = service.okrs.get_org_node(node_id)
    if not node or node.org_id != auth.org_id:
        raise HTTPException(status_code=404, detail="Org node not found")
    return node


def _period_for_auth(period_id: str, auth: AuthContext):
    period = service.okrs.get_period(period_id)
    if not period or period.org_id != auth.org_id:
        raise HTTPException(status_code=404, detail="Period not found")
    return period


def _objective_for_auth(objective_id: str, auth: AuthContext):
    obj = service.okrs.get_objective(objective_id)
    if not obj or obj.org_id != auth.org_id:
        raise HTTPException(status_code=404, detail="Objective not found")
    return obj


def _kpi_for_auth(kpi_id: str, auth: AuthContext):
    kpi = service.okrs.get_kpi(kpi_id)
    if not kpi or kpi.org_id != auth.org_id:
        raise HTTPException(status_code=404, detail="KPI not found")
    return kpi


def _initiative_for_auth(initiative_id: str, auth: AuthContext):
    initiative = service.okrs._get_initiative(initiative_id)
    if not initiative or initiative.org_id != auth.org_id:
        raise HTTPException(status_code=404, detail="Initiative not found")
    return initiative


# ── Pydantic models ──────────────────────────────────────────────────────────

class OrgNodeCreate(BaseModel):
    name: str
    node_type: str = "team"
    parent_id: Optional[str] = None
    org_id: str = "org-1"
    owner_user_id: str = "user-1"

class OrgNodeUpdate(BaseModel):
    name: Optional[str] = None
    node_type: Optional[str] = None
    parent_id: Optional[str] = None
    active_period_id: Optional[str] = None
    owner_user_id: Optional[str] = None

class PeriodCreate(BaseModel):
    name: str
    period_type: str = "quarterly"
    fiscal_year: int
    quarter: Optional[int] = None
    start_date: str
    end_date: str
    org_id: str = "org-1"

class PeriodUpdate(BaseModel):
    status: Optional[str] = None
    name: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class ObjectiveCreate(BaseModel):
    period_id: str
    org_node_id: str = "node-company"
    title: str
    objective_type: str = "committed"
    owner_user_id: str = "user-1"
    org_id: str = "org-1"
    description: str = ""
    rationale: str = ""
    parent_objective_id: Optional[str] = None
    sponsor_user_id: Optional[str] = None
    visibility: str = "public_internal"
    alignment_mode: str = "inherited"

class ObjectiveUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    rationale: Optional[str] = None
    objective_type: Optional[str] = None
    status: Optional[str] = None
    owner_user_id: Optional[str] = None
    sponsor_user_id: Optional[str] = None
    parent_objective_id: Optional[str] = None
    visibility: Optional[str] = None
    alignment_mode: Optional[str] = None
    confidence_current: Optional[float] = None
    quality_score: Optional[int] = None
    quality_notes: Optional[str] = None

class ObjectiveGrade(BaseModel):
    grade: float
    retrospective: str = ""
    carry_forward: bool = False
    next_period_id: Optional[str] = None

class KeyResultCreate(BaseModel):
    title: str
    kr_type: str = "metric"
    owner_user_id: str = "user-1"
    org_id: str = "org-1"
    description: str = ""
    metric_name: Optional[str] = None
    metric_definition: Optional[str] = None
    data_source_type: str = "manual"
    source_reference: Optional[str] = None
    baseline_value: Optional[float] = None
    target_value: Optional[float] = None
    unit: str = ""
    direction: str = "increase"
    weighting: float = 1.0
    checkin_frequency: str = "weekly"
    due_date: Optional[str] = None

class KeyResultUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    kr_type: Optional[str] = None
    current_value: Optional[float] = None
    target_value: Optional[float] = None
    baseline_value: Optional[float] = None
    unit: Optional[str] = None
    direction: Optional[str] = None
    weighting: Optional[float] = None
    status: Optional[str] = None
    confidence_current: Optional[float] = None
    risk_reason: Optional[str] = None
    due_date: Optional[str] = None

class CheckinCreate(BaseModel):
    current_value: Optional[float] = None
    confidence: Optional[float] = None
    blockers: str = ""
    decisions_needed: str = ""
    narrative_update: str = ""
    next_steps: str = ""
    checkin_date: Optional[str] = None
    org_id: str = "org-1"
    user_id: str = "user-1"
    parent_checkin_id: Optional[str] = None   # set when creating a correction/update

class KPICreate(BaseModel):
    name: str
    unit: str = ""
    org_id: str = "org-1"
    org_node_id: Optional[str] = None
    description: str = ""
    metric_definition: str = ""
    source_reference: str = ""
    target_band_low: Optional[float] = None
    target_band_high: Optional[float] = None
    update_frequency: str = "monthly"
    owner_user_id: str = "user-1"

class KPIUpdate(BaseModel):
    name: Optional[str] = None
    unit: Optional[str] = None
    description: Optional[str] = None
    metric_definition: Optional[str] = None
    source_reference: Optional[str] = None
    target_band_low: Optional[float] = None
    target_band_high: Optional[float] = None
    update_frequency: Optional[str] = None
    owner_user_id: Optional[str] = None

class KPIRecordValue(BaseModel):
    value: float
    org_id: str = "org-1"

class KPILink(BaseModel):
    kpi_id: str
    link_type: str = "derived_from"
    contribution_notes: str = ""

class DependencyCreate(BaseModel):
    source_object_type: str
    source_object_id: str
    target_object_type: str
    target_object_id: str
    dependency_type: str = "contributes_to"
    severity: str = "medium"
    org_id: str = "org-1"

class InitiativeCreate(BaseModel):
    title: str
    description: str = ""
    owner_user_id: str = "user-1"
    org_id: str = "org-1"
    status: str = "not_started"
    external_system_ref: Optional[str] = None

class InitiativeUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    owner_user_id: Optional[str] = None
    external_system_ref: Optional[str] = None

class MeetingGenerate(BaseModel):
    meeting_type: str = "weekly_checkin"
    org_node_id: Optional[str] = None
    period_id: Optional[str] = None
    org_id: str = "org-1"


# ── Org Nodes ────────────────────────────────────────────────────────────────

@router.get("/okrs/org-nodes")
async def list_org_nodes(request: Request, org_id: str = Query("org-1")):
    auth = _auth(request)
    nodes = service.okrs.list_org_nodes(org_id=auth.org_id)
    return {"org_nodes": [asdict(n) for n in nodes]}


@router.post("/okrs/org-nodes")
async def create_org_node(body: OrgNodeCreate, request: Request):
    auth = _auth(request)
    node = service.okrs.create_org_node(
        name=body.name,
        node_type=body.node_type,
        parent_id=body.parent_id,
        org_id=auth.org_id,
        owner_user_id=auth.user_id,
    )
    return asdict(node)


@router.get("/okrs/org-nodes/{node_id}")
async def get_org_node(node_id: str, request: Request):
    auth = _auth(request)
    node = _org_node_for_auth(node_id, auth)
    return asdict(node)


@router.put("/okrs/org-nodes/{node_id}")
async def update_org_node(node_id: str, body: OrgNodeUpdate, request: Request):
    auth = _auth(request)
    _org_node_for_auth(node_id, auth)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    updated = service.okrs.update_org_node(node_id, **updates)
    return asdict(updated)


@router.get("/okrs/org-nodes/{node_id}/tree")
async def get_org_subtree(node_id: str, request: Request, org_id: str = Query("org-1")):
    auth = _auth(request)
    _org_node_for_auth(node_id, auth)
    return service.okrs.get_org_tree(org_id=auth.org_id, root_node_id=node_id)


# ── OKR Periods ──────────────────────────────────────────────────────────────

@router.get("/okrs/periods")
async def list_periods(
    request: Request,
    org_id: str = Query("org-1"),
    status: Optional[str] = Query(None),
):
    auth = _auth(request)
    periods = service.okrs.list_periods(org_id=auth.org_id, status=status)
    return {"periods": [asdict(p) for p in periods]}


@router.post("/okrs/periods")
async def create_period(body: PeriodCreate, request: Request):
    auth = _auth(request)
    period = service.okrs.create_period(
        name=body.name,
        period_type=body.period_type,
        fiscal_year=body.fiscal_year,
        quarter=body.quarter,
        start_date=body.start_date,
        end_date=body.end_date,
        org_id=auth.org_id,
    )
    return asdict(period)


@router.put("/okrs/periods/{period_id}")
async def update_period(period_id: str, body: PeriodUpdate, request: Request):
    auth = _auth(request)
    _period_for_auth(period_id, auth)
    if body.status == "active":
        period = service.okrs.activate_period(period_id)
    elif body.status == "closed":
        period = service.okrs.close_period(period_id)
    else:
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        period = service.okrs.update_period(period_id, **updates)
    return asdict(period)


# ── Objectives ───────────────────────────────────────────────────────────────

@router.get("/okrs/objectives")
async def list_objectives(
    request: Request,
    org_id: str = Query("org-1"),
    period_id: Optional[str] = Query(None),
    org_node_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    objective_type: Optional[str] = Query(None),
    parent_id: Optional[str] = Query(None),
):
    auth = _auth(request)
    objs = service.okrs.list_objectives(
        org_id=auth.org_id,
        period_id=period_id,
        org_node_id=org_node_id,
        status=status,
        objective_type=objective_type,
        parent_objective_id=parent_id,
    )
    return {"objectives": [asdict(o) for o in objs]}


@router.post("/okrs/objectives")
async def create_objective(body: ObjectiveCreate, request: Request):
    auth = _auth(request)
    _period_for_auth(body.period_id, auth)
    _org_node_for_auth(body.org_node_id, auth)
    obj = service.okrs.create_objective(
        period_id=body.period_id,
        org_node_id=body.org_node_id,
        title=body.title,
        objective_type=body.objective_type,
        owner_user_id=auth.user_id,
        org_id=auth.org_id,
        description=body.description,
        rationale=body.rationale,
        parent_objective_id=body.parent_objective_id,
        sponsor_user_id=body.sponsor_user_id,
        visibility=body.visibility,
        alignment_mode=body.alignment_mode,
    )
    # Run validation and return alongside created object
    from packages.okrs.validation import OKRValidator
    validator = OKRValidator()
    existing = service.okrs.list_objectives(
        org_id=auth.org_id, period_id=body.period_id, org_node_id=body.org_node_id
    )
    issues = validator.validate_objective(obj, [o for o in existing if o.objective_id != obj.objective_id])
    return {
        "objective": asdict(obj),
        "validation_issues": [asdict(i) for i in issues],
    }


@router.get("/okrs/objectives/{objective_id}")
async def get_objective(objective_id: str, request: Request):
    auth = _auth(request)
    detail = service.okrs.get_objective_with_details(objective_id)
    obj = detail.get("objective") if detail else None
    if not detail or not obj or obj.get("org_id") != auth.org_id:
        raise HTTPException(status_code=404, detail="Objective not found")
    return detail


@router.put("/okrs/objectives/{objective_id}")
async def update_objective(objective_id: str, body: ObjectiveUpdate, request: Request):
    auth = _auth(request)
    _objective_for_auth(objective_id, auth)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    obj = service.okrs.update_objective(objective_id, **updates)
    return asdict(obj)


@router.delete("/okrs/objectives/{objective_id}")
async def archive_objective(objective_id: str, request: Request):
    auth = _auth(request)
    _objective_for_auth(objective_id, auth)
    obj = service.okrs.archive_objective(objective_id)
    return {"archived": True, "objective_id": obj.objective_id}


@router.get("/okrs/objectives/{objective_id}/hierarchy")
async def get_objective_hierarchy(objective_id: str, request: Request):
    auth = _auth(request)
    _objective_for_auth(objective_id, auth)
    return service.okrs.get_objective_hierarchy(objective_id)


@router.post("/okrs/objectives/{objective_id}/validate")
async def validate_objective(objective_id: str, request: Request):
    from packages.okrs.validation import OKRValidator
    auth = _auth(request)
    obj = _objective_for_auth(objective_id, auth)
    krs = service.okrs.list_key_results(objective_id)
    existing = service.okrs.list_objectives(org_id=obj.org_id, period_id=obj.period_id)
    validator = OKRValidator()
    result = validator.validate_objective_with_krs(
        obj, [o for o in existing if o.objective_id != objective_id], krs
    )
    return {
        "objective_issues": [asdict(i) for i in result["objective"]],
        "kr_issues": {
            kr_id: [asdict(i) for i in issues]
            for kr_id, issues in result["key_results"].items()
        },
    }


@router.post("/okrs/objectives/{objective_id}/grade")
async def grade_objective(objective_id: str, body: ObjectiveGrade, request: Request):
    auth = _auth(request)
    _objective_for_auth(objective_id, auth)
    result = service.okrs.grade_objective(
        objective_id=objective_id,
        grade=body.grade,
        retrospective=body.retrospective,
        carry_forward=body.carry_forward,
        next_period_id=body.next_period_id,
    )
    return result


@router.get("/okrs/objectives/{objective_id}/score")
async def get_objective_score(objective_id: str, request: Request):
    auth = _auth(request)
    _objective_for_auth(objective_id, auth)
    score = service.okrs.compute_objective_score(objective_id)
    return {"objective_id": objective_id, "score": score}


@router.post("/okrs/objectives/{objective_id}/checkins")
async def create_objective_checkin(objective_id: str, body: CheckinCreate, request: Request):
    auth = _auth(request)
    _objective_for_auth(objective_id, auth)
    checkin = service.okrs.add_checkin(
        object_type="objective",
        object_id=objective_id,
        user_id=auth.user_id,
        checkin_date=body.checkin_date,
        current_value=body.current_value,
        confidence=body.confidence,
        blockers=body.blockers,
        decisions_needed=body.decisions_needed,
        narrative_update=body.narrative_update,
        next_steps=body.next_steps,
        org_id=auth.org_id,
        parent_checkin_id=body.parent_checkin_id,
    )
    return asdict(checkin)


# ── Key Results ──────────────────────────────────────────────────────────────

@router.post("/okrs/objectives/{objective_id}/key-results")
async def create_key_result(objective_id: str, body: KeyResultCreate, request: Request):
    auth = _auth(request)
    _objective_for_auth(objective_id, auth)
    kr = service.okrs.create_key_result(
        objective_id=objective_id,
        title=body.title,
        kr_type=body.kr_type,
        owner_user_id=auth.user_id,
        org_id=auth.org_id,
        description=body.description,
        metric_name=body.metric_name,
        metric_definition=body.metric_definition,
        data_source_type=body.data_source_type,
        source_reference=body.source_reference,
        baseline_value=body.baseline_value,
        target_value=body.target_value,
        unit=body.unit,
        direction=body.direction,
        weighting=body.weighting,
        checkin_frequency=body.checkin_frequency,
        due_date=body.due_date,
    )
    return asdict(kr)


@router.put("/okrs/key-results/{kr_id}")
async def update_key_result(kr_id: str, body: KeyResultUpdate, request: Request):
    auth = _auth(request)
    kr = service.okrs.get_key_result(kr_id)
    if not kr or kr.org_id != auth.org_id:
        raise HTTPException(status_code=404, detail="Key result not found")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    kr = service.okrs.update_key_result(kr_id, **updates)
    return asdict(kr)


@router.delete("/okrs/key-results/{kr_id}")
async def delete_key_result(kr_id: str, request: Request):
    auth = _auth(request)
    kr = service.okrs.get_key_result(kr_id)
    if not kr or kr.org_id != auth.org_id:
        raise HTTPException(status_code=404, detail="Key result not found")
    ok = service.okrs.delete_key_result(kr_id)
    return {"deleted": ok, "kr_id": kr_id}


@router.post("/okrs/key-results/{kr_id}/checkins")
async def create_kr_checkin(kr_id: str, body: CheckinCreate, request: Request):
    auth = _auth(request)
    kr = service.okrs.get_key_result(kr_id)
    if not kr or kr.org_id != auth.org_id:
        raise HTTPException(status_code=404, detail="Key result not found")
    checkin = service.okrs.add_checkin(
        object_type="key_result",
        object_id=kr_id,
        user_id=auth.user_id,
        checkin_date=body.checkin_date,
        current_value=body.current_value,
        confidence=body.confidence,
        blockers=body.blockers,
        decisions_needed=body.decisions_needed,
        narrative_update=body.narrative_update,
        next_steps=body.next_steps,
        org_id=auth.org_id,
        parent_checkin_id=body.parent_checkin_id,
    )
    return asdict(checkin)


@router.post("/okrs/key-results/{kr_id}/link-kpi")
async def link_kpi_to_kr(kr_id: str, body: KPILink, request: Request):
    auth = _auth(request)
    kr = service.okrs.get_key_result(kr_id)
    if not kr or kr.org_id != auth.org_id:
        raise HTTPException(status_code=404, detail="Key result not found")
    _kpi_for_auth(body.kpi_id, auth)
    link = service.okrs.link_kr_to_kpi(
        kr_id=kr_id,
        kpi_id=body.kpi_id,
        link_type=body.link_type,
        contribution_notes=body.contribution_notes,
    )
    return asdict(link)


@router.delete("/okrs/key-results/{kr_id}/link-kpi/{kpi_id}")
async def unlink_kpi_from_kr(kr_id: str, kpi_id: str, request: Request):
    auth = _auth(request)
    kr = service.okrs.get_key_result(kr_id)
    if not kr or kr.org_id != auth.org_id:
        raise HTTPException(status_code=404, detail="Key result not found")
    _kpi_for_auth(kpi_id, auth)
    ok = service.okrs.unlink_kr_kpi(kr_id=kr_id, kpi_id=kpi_id)
    return {"unlinked": ok}


# ── Check-ins ────────────────────────────────────────────────────────────────

@router.get("/okrs/checkins")
async def list_checkins(
    object_type: str = Query(...),
    object_id: str = Query(...),
    limit: int = Query(20),
):
    checkins = service.okrs.list_checkins(
        object_type=object_type,
        object_id=object_id,
        limit=limit,
    )
    return {"checkins": [asdict(c) for c in checkins]}


@router.get("/okrs/overdue-checkins")
async def list_overdue_checkins(
    request: Request,
    org_id: str = Query("org-1"),
    days: int = Query(10),
):
    auth = _auth(request)
    krs = service.okrs.list_overdue_checkins(org_id=auth.org_id, days=days)
    return {"overdue_key_results": [asdict(k) for k in krs], "count": len(krs)}


# ── KPIs ─────────────────────────────────────────────────────────────────────

@router.get("/okrs/kpis")
async def list_kpis(
    request: Request,
    org_id: str = Query("org-1"),
    org_node_id: Optional[str] = Query(None),
):
    auth = _auth(request)
    kpis = service.okrs.list_kpis(org_id=auth.org_id, org_node_id=org_node_id)
    return {"kpis": [asdict(k) for k in kpis]}


@router.post("/okrs/kpis")
async def create_kpi(body: KPICreate, request: Request):
    auth = _auth(request)
    kpi = service.okrs.create_kpi(
        name=body.name,
        unit=body.unit,
        org_id=auth.org_id,
        org_node_id=body.org_node_id,
        description=body.description,
        metric_definition=body.metric_definition,
        source_reference=body.source_reference,
        target_band_low=body.target_band_low,
        target_band_high=body.target_band_high,
        update_frequency=body.update_frequency,
        owner_user_id=auth.user_id,
    )
    return asdict(kpi)


@router.put("/okrs/kpis/{kpi_id}")
async def update_kpi(kpi_id: str, body: KPIUpdate, request: Request):
    auth = _auth(request)
    _kpi_for_auth(kpi_id, auth)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    kpi = service.okrs.update_kpi(kpi_id, **updates)
    return asdict(kpi)


@router.post("/okrs/kpis/{kpi_id}/record")
async def record_kpi_value(kpi_id: str, body: KPIRecordValue, request: Request):
    auth = _auth(request)
    _kpi_for_auth(kpi_id, auth)
    kpi = service.okrs.record_kpi_value(kpi_id=kpi_id, value=body.value)
    return asdict(kpi)


@router.get("/okrs/kpis/{kpi_id}/trend")
async def get_kpi_trend(kpi_id: str, request: Request, limit: int = Query(30)):
    auth = _auth(request)
    _kpi_for_auth(kpi_id, auth)
    return service.okrs.get_kpi_trend(kpi_id=kpi_id, limit=limit)


# ── Dependencies ─────────────────────────────────────────────────────────────

@router.post("/okrs/dependencies")
async def create_dependency(body: DependencyCreate, request: Request):
    auth = _auth(request)
    dep = service.okrs.create_dependency(
        source_type=body.source_object_type,
        source_id=body.source_object_id,
        target_type=body.target_object_type,
        target_id=body.target_object_id,
        dep_type=body.dependency_type,
        severity=body.severity,
        org_id=auth.org_id,
    )
    return asdict(dep)


@router.get("/okrs/dependencies")
async def list_dependencies(
    source_id: Optional[str] = Query(None),
    target_id: Optional[str] = Query(None),
    object_type: Optional[str] = Query(None),
    object_id: Optional[str] = Query(None),
):
    oid = object_id or source_id or target_id or ""
    otype = object_type or "objective"
    deps = service.okrs.list_dependencies(object_type=otype, object_id=oid)
    return {"dependencies": [asdict(d) for d in deps]}


@router.delete("/okrs/dependencies/{dep_id}")
async def delete_dependency(dep_id: str, request: Request):
    ok = service.okrs.delete_dependency(dep_id)
    return {"deleted": ok, "dependency_id": dep_id}


# ── Initiatives ──────────────────────────────────────────────────────────────

@router.get("/okrs/initiatives")
async def list_initiatives(
    request: Request,
    org_id: str = Query("org-1"),
    objective_id: Optional[str] = Query(None),
    kr_id: Optional[str] = Query(None),
):
    auth = _auth(request)
    initiatives = service.okrs.list_initiatives(
        org_id=auth.org_id, objective_id=objective_id, kr_id=kr_id
    )
    return {"initiatives": [asdict(i) for i in initiatives]}


@router.post("/okrs/objectives/{objective_id}/initiatives")
async def create_initiative(objective_id: str, body: InitiativeCreate, request: Request):
    auth = _auth(request)
    _objective_for_auth(objective_id, auth)
    initiative = service.okrs.create_initiative(
        title=body.title,
        owner_user_id=auth.user_id,
        linked_objective_id=objective_id,
        linked_key_result_id=None,
        org_id=auth.org_id,
        description=body.description,
        status=body.status,
        external_system_ref=body.external_system_ref,
    )
    return asdict(initiative)


@router.put("/okrs/initiatives/{initiative_id}")
async def update_initiative(initiative_id: str, body: InitiativeUpdate, request: Request):
    auth = _auth(request)
    _initiative_for_auth(initiative_id, auth)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    initiative = service.okrs.update_initiative(initiative_id, **updates)
    return asdict(initiative)


# ── Alignment ────────────────────────────────────────────────────────────────

@router.get("/okrs/alignment-graph")
async def get_alignment_graph(
    request: Request,
    org_id: str = Query("org-1"),
    period_id: Optional[str] = Query(None),
):
    auth = _auth(request)
    return service.okrs.get_alignment_graph(org_id=auth.org_id, period_id=period_id)


# ── Dashboards ───────────────────────────────────────────────────────────────

@router.get("/okrs/dashboard/executive")
async def executive_dashboard(
    request: Request,
    org_id: str = Query("org-1"),
    period_id: Optional[str] = Query(None),
):
    auth = _auth(request)
    return service.okrs.executive_dashboard(org_id=auth.org_id, period_id=period_id)


@router.get("/okrs/dashboard/portfolio")
async def portfolio_dashboard(
    org_node_id: str = Query("node-company"),
    period_id: Optional[str] = Query(None),
):
    return service.okrs.portfolio_dashboard(org_node_id=org_node_id, period_id=period_id)


@router.get("/okrs/dashboard/team/{node_id}")
async def team_dashboard(
    node_id: str,
    period_id: Optional[str] = Query(None),
):
    return service.okrs.team_dashboard(org_node_id=node_id, period_id=period_id)


@router.get("/okrs/dashboard/analytics")
async def analytics_dashboard(
    request: Request,
    org_id: str = Query("org-1"),
):
    auth = _auth(request)
    return service.okrs.analytics_dashboard(org_id=auth.org_id)


# ── Meetings ─────────────────────────────────────────────────────────────────

@router.post("/okrs/meetings/generate")
async def generate_meeting(body: MeetingGenerate, request: Request):
    auth = _auth(request)
    artifact = service.okrs.generate_meeting_artifact(
        meeting_type=body.meeting_type,
        org_node_id=body.org_node_id,
        period_id=body.period_id,
        org_id=auth.org_id,
    )
    return asdict(artifact)


@router.get("/okrs/meetings")
async def list_meeting_artifacts(
    request: Request,
    org_id: str = Query("org-1"),
    meeting_type: Optional[str] = Query(None),
):
    auth = _auth(request)
    artifacts = service.okrs.list_meeting_artifacts(org_id=auth.org_id, meeting_type=meeting_type)
    return {"artifacts": [asdict(a) for a in artifacts]}
