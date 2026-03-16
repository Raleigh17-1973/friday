from __future__ import annotations

from dataclasses import asdict
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from apps.api.deps import service
from apps.api.security import AuthContext

router = APIRouter()


def _auth(request: Request) -> AuthContext:
    return getattr(request.state, "auth", None) or AuthContext(
        user_id="user-1", org_id="org-1", roles=["user"]
    )


class QATestCasePayload(BaseModel):
    title: str
    feature_area: str
    test_type: str
    org_id: str = "default"
    subfeature: str = ""
    description: str = ""
    preconditions: str = ""
    steps: list[str] = []
    expected_result: str = ""
    priority: str = "medium"
    severity_if_fails: str = "major"
    applies_to_agents: list[str] = []
    applies_to_ui_surfaces: list[str] = []
    release_blocker: bool = False
    status: str = "draft"
    created_by: str = "qa-specialist"
    linked_user_story_ids: list[str] = []
    linked_bug_ids: list[str] = []
    linked_workspace_ids: list[str] = []
    notes: str = ""
    tags: list[str] = []


class QASuitePayload(BaseModel):
    name: str
    suite_type: str
    org_id: str = "default"
    description: str = ""
    feature_areas: list[str] = []
    test_case_ids: list[str] = []
    generated_by_rule: str = ""
    owner: str = ""


class QASuiteGeneratePayload(BaseModel):
    name: str
    rule: str
    org_id: str = "default"
    owner: str = ""


class QARunPayload(BaseModel):
    suite_id: str
    title: str
    org_id: str = "default"
    environment: str = "development"
    triggered_by: str = "manual"
    run_type: str = "manual"
    notes: str = ""


class QAResultPayload(BaseModel):
    test_case_id: str
    result: str
    findings: str = ""
    reproduction_notes: str = ""
    severity: Optional[str] = None
    linked_bug_id: Optional[str] = None
    should_become_regression: bool = False
    tester: str = ""


class QABugPayload(BaseModel):
    title: str
    org_id: str = "default"
    severity: str = "major"
    category: str = "functional"
    area: str = ""
    repro_steps: list[str] = []
    expected_result: str = ""
    actual_result: str = ""
    impact: str = ""
    recommended_fix: str = ""
    release_blocker: bool = False
    linked_test_case_ids: list[str] = []
    linked_run_ids: list[str] = []
    owner: str = ""


class QAStoryPayload(BaseModel):
    title: str
    org_id: str = "default"
    user_story: str = ""
    context: str = ""
    acceptance_criteria: list[str] = []
    priority: str = "medium"
    dependencies: list[str] = []
    source_test_case_id: Optional[str] = None
    source_run_id: Optional[str] = None


# ─── Test Case Routes ────────────────────────────────────────────────────────

@router.get("/qa/tests")
def list_qa_tests(
    org_id: str = "default",
    feature_area: Optional[str] = None,
    test_type: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    release_blocker: Optional[bool] = None,
    search: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict]:
    tests = service.qa.list_test_cases(
        org_id=org_id, feature_area=feature_area, test_type=test_type,
        status=status, priority=priority, release_blocker=release_blocker,
        search=search, limit=limit, offset=offset,
    )
    return [asdict(t) for t in tests]


@router.post("/qa/tests")
def create_qa_test(payload: QATestCasePayload) -> dict:
    tc = service.qa.create_test_case(**payload.model_dump())
    return asdict(tc)


@router.get("/qa/tests/{tc_id}")
def get_qa_test(tc_id: str) -> dict:
    tc = service.qa.get_test_case(tc_id)
    if not tc:
        raise HTTPException(status_code=404, detail="Test case not found")
    return asdict(tc)


@router.put("/qa/tests/{tc_id}")
def update_qa_test(tc_id: str, updates: dict[str, Any], updated_by: str = "qa-specialist") -> dict:
    tc = service.qa.update_test_case(tc_id, updates, updated_by=updated_by)
    if not tc:
        raise HTTPException(status_code=404, detail="Test case not found")
    return asdict(tc)


@router.post("/qa/tests/{tc_id}/deprecate")
def deprecate_qa_test(tc_id: str, updated_by: str = "qa-specialist") -> dict:
    ok = service.qa.deprecate_test_case(tc_id, updated_by=updated_by)
    if not ok:
        raise HTTPException(status_code=404, detail="Test case not found")
    return {"status": "deprecated", "tc_id": tc_id}


@router.post("/qa/tests/{tc_id}/clone")
def clone_qa_test(tc_id: str, new_title: Optional[str] = None, created_by: str = "qa-specialist") -> dict:
    tc = service.qa.clone_test_case(tc_id, new_title=new_title, created_by=created_by)
    if not tc:
        raise HTTPException(status_code=404, detail="Test case not found")
    return asdict(tc)


# ─── Suite Routes ────────────────────────────────────────────────────────────

@router.get("/qa/suites")
def list_qa_suites(org_id: str = "default", status: Optional[str] = None) -> list[dict]:
    return [asdict(s) for s in service.qa.list_suites(org_id=org_id, status=status)]


@router.post("/qa/suites")
def create_qa_suite(payload: QASuitePayload) -> dict:
    suite = service.qa.create_suite(**payload.model_dump())
    return asdict(suite)


@router.get("/qa/suites/{suite_id}")
def get_qa_suite(suite_id: str) -> dict:
    suite = service.qa.get_suite(suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="Suite not found")
    # Enrich with full test case objects
    result = asdict(suite)
    result["test_cases"] = [
        asdict(tc) for tc in [service.qa.get_test_case(tid) for tid in suite.test_case_ids]
        if tc is not None
    ]
    return result


@router.put("/qa/suites/{suite_id}")
def update_qa_suite(suite_id: str, updates: dict[str, Any]) -> dict:
    suite = service.qa.update_suite(suite_id, updates)
    if not suite:
        raise HTTPException(status_code=404, detail="Suite not found")
    return asdict(suite)


@router.post("/qa/suites/generate")
def generate_qa_suite(payload: QASuiteGeneratePayload) -> dict:
    suite = service.qa.generate_suite_from_rules(
        name=payload.name, rule=payload.rule,
        org_id=payload.org_id, owner=payload.owner,
    )
    return asdict(suite)


# ─── Run Routes ──────────────────────────────────────────────────────────────

@router.get("/qa/runs")
def list_qa_runs(org_id: str = "default", suite_id: Optional[str] = None, limit: int = 50) -> list[dict]:
    return [asdict(r) for r in service.qa.list_runs(org_id=org_id, suite_id=suite_id, limit=limit)]


@router.post("/qa/runs")
def create_qa_run(payload: QARunPayload) -> dict:
    run = service.qa.create_test_run(**payload.model_dump())
    return asdict(run)


@router.get("/qa/runs/{run_id}")
def get_qa_run(run_id: str) -> dict:
    run = service.qa.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    result = asdict(run)
    result["results"] = [asdict(r) for r in service.qa.list_test_results(run_id)]
    return result


@router.post("/qa/runs/{run_id}/results")
def store_qa_result(run_id: str, payload: QAResultPayload) -> dict:
    result = service.qa.store_test_result(run_id=run_id, **payload.model_dump())
    return asdict(result)


@router.post("/qa/runs/{run_id}/complete")
def complete_qa_run(run_id: str, summary: str = "", notes: str = "") -> dict:
    run = service.qa.complete_test_run(run_id, summary=summary, notes=notes)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return asdict(run)


# ─── Bug Report Routes ───────────────────────────────────────────────────────

@router.get("/qa/bugs")
def list_qa_bugs(org_id: str = "default", status: Optional[str] = None, area: Optional[str] = None) -> list[dict]:
    return [asdict(b) for b in service.qa.list_bug_reports(org_id=org_id, status=status, area=area)]


@router.post("/qa/bugs")
def create_qa_bug(payload: QABugPayload) -> dict:
    bug = service.qa.create_bug_report(**payload.model_dump())
    return asdict(bug)


@router.put("/qa/bugs/{bug_id}")
def update_qa_bug(bug_id: str, updates: dict[str, Any]) -> dict:
    bug = service.qa.update_bug_report(bug_id, updates)
    if not bug:
        raise HTTPException(status_code=404, detail="Bug report not found")
    return asdict(bug)


# ─── User Story Routes ───────────────────────────────────────────────────────

@router.get("/qa/stories")
def list_qa_stories(org_id: str = "default", status: Optional[str] = None) -> list[dict]:
    return [asdict(s) for s in service.qa.list_user_story_candidates(org_id=org_id, status=status)]


@router.post("/qa/stories")
def create_qa_story(payload: QAStoryPayload) -> dict:
    story = service.qa.create_user_story_candidate(**payload.model_dump())
    return asdict(story)


# ─── Coverage Gap Analysis ───────────────────────────────────────────────────

@router.get("/qa/coverage")
def get_qa_coverage(org_id: str = "default") -> dict:
    report = service.qa.analyze_coverage_gaps(org_id=org_id)
    result = asdict(report)
    result["gaps"] = [asdict(g) for g in report.gaps]
    return result


# ─── Registry Summary ────────────────────────────────────────────────────────

@router.get("/qa/summary")
def get_qa_summary(org_id: str = "default") -> dict:
    return service.qa.get_registry_summary(org_id=org_id)


# ─── Seed Templates ──────────────────────────────────────────────────────────

@router.post("/qa/templates/seed")
def seed_qa_templates(org_id: str = "default") -> dict:
    """Force re-seed default templates (useful after schema changes)."""
    service.qa._seed_templates()
    summary = service.qa.get_registry_summary(org_id=org_id)
    return {"status": "seeded", "total": summary["total"]}


# ─── Regression Candidates ───────────────────────────────────────────────────

@router.get("/qa/regression-candidates")
def get_regression_candidates(org_id: str = "default") -> list[dict]:
    return [asdict(r) for r in service.qa.get_regression_candidates(org_id=org_id)]
