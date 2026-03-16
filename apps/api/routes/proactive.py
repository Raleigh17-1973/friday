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


@router.get("/alerts")
def list_alerts(org_id: str = "org-1", severity: Optional[str] = None) -> list[dict]:
    return [asdict(a) for a in service.scanner.list_alerts(org_id=org_id, severity=severity)]


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str) -> dict:
    service.scanner.acknowledge(alert_id)
    return {"status": "acknowledged"}


@router.post("/alerts/scan")
def run_proactive_scan(org_id: str = "org-1") -> dict:
    # Build scanner-compatible KPI dicts: scanner expects current_value, target_value, kpi_id, org_id
    kpi_status_list = service.kpis.kpi_status(org_id=org_id)
    scanner_kpis = [
        {
            "kpi_id": k.get("kpi_id", ""),
            "name": k.get("name", ""),
            "current_value": k.get("latest_value"),
            "target_value": k.get("target"),
            "unit": k.get("unit", ""),
            "org_id": k.get("org_id", org_id),
            "higher_is_better": True,
        }
        for k in kpi_status_list
    ]
    # Build scanner-compatible OKR dicts: scanner expects title, progress_pct, due_date, org_id
    objectives_raw = service.okrs.list_objectives(org_id=org_id)
    scanner_okrs = [
        {
            "title": o.name,
            "progress_pct": o.progress * 100,
            "due_date": None,
            "org_id": o.org_id,
            "objective_id": o.obj_id,
        }
        for o in objectives_raw
    ]
    budget_status = service.budgets.budget_status(org_id=org_id)

    kpi_alerts = service.scanner.scan_kpis(scanner_kpis)
    okr_alerts = service.scanner.scan_okrs(scanner_okrs)
    budget_alerts = service.scanner.scan_budget(budget_status)
    all_alerts = kpi_alerts + okr_alerts + budget_alerts

    return {
        "scanned": {"kpis": len(scanner_kpis), "objectives": len(scanner_okrs), "budget_categories": len(budget_status)},
        "alerts_generated": len(all_alerts),
        "alerts": [asdict(a) for a in all_alerts],
    }


@router.get("/digest/weekly")
def weekly_digest(org_id: str = "org-1") -> dict:
    # Normalize KPIs: digest expects current_value, target_value
    kpi_status_list = service.kpis.kpi_status(org_id=org_id)
    digest_kpis = [
        {
            "name": k.get("name", ""),
            "current_value": k.get("latest_value", 0) or 0,
            "target_value": k.get("target") or 1,
            "unit": k.get("unit", ""),
            "status": "on_track" if k.get("on_target") else "at_risk",
        }
        for k in kpi_status_list
    ]
    # Normalize OKRs: digest expects title, progress_pct (0-100), status
    digest_objectives = [
        {
            "title": o.name,
            "progress_pct": o.progress * 100,
            "status": o.status,
        }
        for o in service.okrs.list_objectives(org_id=org_id)
    ]
    alerts = [asdict(a) for a in service.scanner.list_alerts(org_id=org_id)]
    decisions = [asdict(d) for d in service.decisions.list_decisions(org_id=org_id, limit=10)]

    digest = service.digest.generate_weekly(digest_kpis, digest_objectives, alerts, decisions, org_id=org_id)
    result = asdict(digest)
    result["markdown"] = service.digest.digest_to_markdown(digest)
    return result


@router.get("/events")
def list_events(limit: int = 50) -> list[dict]:
    return [asdict(e) for e in service.events.recent_events(limit=limit)]
