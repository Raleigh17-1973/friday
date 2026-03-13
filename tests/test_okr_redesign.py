"""Tests for the redesigned OKR service with 3-level hierarchy and rich schema."""
from __future__ import annotations

import pytest
from pathlib import Path
from packages.okrs.service import OKRService


@pytest.fixture
def svc(tmp_path: Path) -> OKRService:
    return OKRService(db_path=tmp_path / "okrs_test.db")


# ---------------------------------------------------------------------------
# 3-level hierarchy: Company → Team → Individual
# ---------------------------------------------------------------------------
class TestObjectiveHierarchyThreeLevels:
    def test_create_company_objective(self, svc: OKRService):
        obj = svc.create_objective(
            org_id="org1", title="Achieve market leadership", level="company",
            owner="ceo", period="2026-Q1"
        )
        assert obj.level == "company"
        assert obj.parent_id is None
        assert obj.obj_id

    def test_create_team_objective_under_company(self, svc: OKRService):
        company = svc.create_objective(
            org_id="org1", title="Company goal", level="company",
            owner="ceo", period="2026-Q1"
        )
        team = svc.create_objective(
            org_id="org1", title="Engineering goal", level="team",
            owner="eng_lead", period="2026-Q1", parent_id=company.obj_id
        )
        assert team.parent_id == company.obj_id
        assert team.level == "team"

    def test_create_individual_objective_under_team(self, svc: OKRService):
        company = svc.create_objective(org_id="org1", title="Company", level="company", owner="ceo", period="2026-Q1")
        team = svc.create_objective(org_id="org1", title="Team", level="team", owner="lead", period="2026-Q1", parent_id=company.obj_id)
        individual = svc.create_objective(org_id="org1", title="Individual", level="individual", owner="alice", period="2026-Q1", parent_id=team.obj_id)
        assert individual.parent_id == team.obj_id
        assert individual.level == "individual"

    def test_get_children(self, svc: OKRService):
        parent = svc.create_objective(org_id="org1", title="Parent", level="company", owner="ceo", period="2026-Q1")
        child1 = svc.create_objective(org_id="org1", title="Child 1", level="team", owner="lead1", period="2026-Q1", parent_id=parent.obj_id)
        child2 = svc.create_objective(org_id="org1", title="Child 2", level="team", owner="lead2", period="2026-Q1", parent_id=parent.obj_id)
        children = svc.get_children(parent.obj_id, org_id="org1")
        child_ids = [c.obj_id for c in children]
        assert child1.obj_id in child_ids
        assert child2.obj_id in child_ids

    def test_company_obj_has_no_children_initially(self, svc: OKRService):
        obj = svc.create_objective(org_id="org1", title="Company", level="company", owner="ceo", period="2026-Q1")
        children = svc.get_children(obj.obj_id, org_id="org1")
        assert children == []

    def test_list_objectives_by_level(self, svc: OKRService):
        svc.create_objective(org_id="org1", title="Comp obj", level="company", owner="ceo", period="2026-Q1")
        svc.create_objective(org_id="org1", title="Team obj", level="team", owner="lead", period="2026-Q1")
        company_objs = svc.list_objectives(org_id="org1", level="company")
        assert all(o.level == "company" for o in company_objs)
        team_objs = svc.list_objectives(org_id="org1", level="team")
        assert all(o.level == "team" for o in team_objs)


# ---------------------------------------------------------------------------
# Key Result full schema
# ---------------------------------------------------------------------------
class TestKeyResultFullSchema:
    def test_create_key_result(self, svc: OKRService):
        obj = svc.create_objective(org_id="org1", title="Grow revenue", level="company", owner="ceo", period="2026-Q1")
        kr = svc.create_key_result(
            objective_id=obj.obj_id,
            title="Monthly Recurring Revenue",
            metric_type="currency",
            baseline=500_000.0,
            target_value=750_000.0,
            unit="USD",
            owner="cfo",
        )
        assert kr.metric_type == "currency"
        assert kr.baseline == 500_000.0
        assert kr.target_value == 750_000.0
        assert kr.unit == "USD"
        assert kr.owner == "cfo"
        assert kr.kr_id

    def test_create_percentage_kr(self, svc: OKRService):
        obj = svc.create_objective(org_id="org1", title="Improve NPS", level="company", owner="ceo", period="2026-Q1")
        kr = svc.create_key_result(
            objective_id=obj.obj_id, title="NPS Score", metric_type="percentage",
            baseline=30.0, target_value=60.0, unit="%", owner="cx"
        )
        assert kr.metric_type == "percentage"
        assert kr.baseline == 30.0

    def test_update_key_result_current_value(self, svc: OKRService):
        obj = svc.create_objective(org_id="org1", title="Grow", level="company", owner="ceo", period="2026-Q1")
        kr = svc.create_key_result(objective_id=obj.obj_id, title="Revenue", metric_type="currency", baseline=0, target_value=100, unit="USD", owner="cfo")
        updated = svc.update_key_result(kr.kr_id, current_value=60.0, notes="On track after Q1 push")
        assert updated is not None
        assert updated.current_value == 60.0
        assert updated.notes == "On track after Q1 push"

    def test_list_key_results_for_objective(self, svc: OKRService):
        obj = svc.create_objective(org_id="org1", title="Goal", level="company", owner="ceo", period="2026-Q1")
        svc.create_key_result(objective_id=obj.obj_id, title="KR1", metric_type="number", baseline=0, target_value=10, unit="count", owner="alice")
        svc.create_key_result(objective_id=obj.obj_id, title="KR2", metric_type="percentage", baseline=0, target_value=100, unit="%", owner="bob")
        krs = svc.list_key_results(obj.obj_id)
        assert len(krs) == 2
        titles = [kr.title for kr in krs]
        assert "KR1" in titles and "KR2" in titles

    def test_kr_progress_property(self, svc: OKRService):
        obj = svc.create_objective(org_id="org1", title="Goal", level="company", owner="ceo", period="2026-Q1")
        kr = svc.create_key_result(objective_id=obj.obj_id, title="KR", metric_type="number", baseline=0, target_value=100, unit="", owner="alice")
        updated = svc.update_key_result(kr.kr_id, current_value=50.0)
        assert updated is not None
        assert updated.progress == pytest.approx(0.5, abs=0.01)


# ---------------------------------------------------------------------------
# Initiatives
# ---------------------------------------------------------------------------
class TestInitiativeCreateAndLink:
    def test_create_initiative(self, svc: OKRService):
        obj = svc.create_objective(org_id="org1", title="Goal", level="company", owner="ceo", period="2026-Q1")
        initiative = svc.create_initiative(
            title="Launch beta program",
            objective_id=obj.obj_id,
            owner="pm",
            org_id="org1",
        )
        assert initiative.title == "Launch beta program"
        assert initiative.objective_id == obj.obj_id
        assert initiative.status == "not_started"
        assert initiative.initiative_id

    def test_list_initiatives(self, svc: OKRService):
        obj = svc.create_objective(org_id="org1", title="Goal", level="company", owner="ceo", period="2026-Q1")
        svc.create_initiative(title="Init 1", objective_id=obj.obj_id, owner="alice", org_id="org1")
        svc.create_initiative(title="Init 2", objective_id=obj.obj_id, owner="bob", org_id="org1")
        initiatives = svc.list_initiatives(obj.obj_id)
        assert len(initiatives) == 2

    def test_initiative_linked_to_kr(self, svc: OKRService):
        obj = svc.create_objective(org_id="org1", title="Goal", level="company", owner="ceo", period="2026-Q1")
        kr = svc.create_key_result(objective_id=obj.obj_id, title="KR", metric_type="number", baseline=0, target_value=100, unit="", owner="alice")
        initiative = svc.create_initiative(
            title="Initiative", objective_id=obj.obj_id,
            owner="bob", org_id="org1", kr_id=kr.kr_id
        )
        assert initiative.kr_id == kr.kr_id

    def test_update_initiative_status(self, svc: OKRService):
        obj = svc.create_objective(org_id="org1", title="Goal", level="company", owner="ceo", period="2026-Q1")
        init = svc.create_initiative(title="Init", objective_id=obj.obj_id, owner="alice", org_id="org1")
        svc.update_initiative(init.initiative_id, status="in_progress")
        initiatives = svc.list_initiatives(obj.obj_id)
        found = next((i for i in initiatives if i.initiative_id == init.initiative_id), None)
        assert found is not None
        assert found.status == "in_progress"


# ---------------------------------------------------------------------------
# Progress from Key Results
# ---------------------------------------------------------------------------
class TestObjectiveProgressFromKeyResults:
    def test_get_objective_returns_data(self, svc: OKRService):
        obj = svc.create_objective(org_id="org1", title="Goal", level="company", owner="ceo", period="2026-Q1")
        svc.create_key_result(objective_id=obj.obj_id, title="KR1", metric_type="percentage", baseline=0, target_value=100, unit="%", owner="alice")
        fetched = svc.get_objective(obj.obj_id)
        assert fetched is not None
        assert fetched.obj_id == obj.obj_id

    def test_objective_with_details(self, svc: OKRService):
        obj = svc.create_objective(org_id="org1", title="Goal", level="company", owner="ceo", period="2026-Q1")
        svc.create_key_result(objective_id=obj.obj_id, title="KR1", metric_type="number", baseline=0, target_value=10, unit="", owner="alice")
        svc.create_initiative(title="Initiative", objective_id=obj.obj_id, owner="bob", org_id="org1")
        details = svc.get_objective_with_details(obj.obj_id)
        assert details is not None
        # The details dict should contain objective + key results + initiatives
        assert "objective" in details
        assert "key_results" in details
        assert len(details["key_results"]) == 1

    def test_okr_summary(self, svc: OKRService):
        svc.create_objective(org_id="org1", title="Company Goal", level="company", owner="ceo", period="2026-Q1")
        svc.create_objective(org_id="org1", title="Team Goal", level="team", owner="lead", period="2026-Q1")
        summary = svc.okr_summary(org_id="org1")
        assert isinstance(summary, dict)
        assert summary.get("total", 0) >= 2


# ---------------------------------------------------------------------------
# Confidence scoring and check-ins
# ---------------------------------------------------------------------------
class TestConfidenceScoring:
    def test_default_confidence_in_range(self, svc: OKRService):
        obj = svc.create_objective(org_id="org1", title="Goal", level="company", owner="ceo", period="2026-Q1")
        assert 0.0 <= obj.confidence <= 1.0

    def test_update_confidence(self, svc: OKRService):
        obj = svc.create_objective(org_id="org1", title="Goal", level="company", owner="ceo", period="2026-Q1")
        updated = svc.update_objective(obj.obj_id, confidence=0.3)
        assert updated is not None
        assert updated.confidence == pytest.approx(0.3, abs=0.01)

    def test_add_checkin(self, svc: OKRService):
        obj = svc.create_objective(org_id="org1", title="Goal", level="company", owner="ceo", period="2026-Q1")
        checkin = svc.add_checkin(
            objective_id=obj.obj_id,
            notes="Progress: hired 2 engineers. Blocker: budget constraints.",
            author="alice",
            status="at_risk",
            confidence=0.4,
        )
        assert checkin.author == "alice"
        assert checkin.confidence == pytest.approx(0.4, abs=0.01)
        assert checkin.status == "at_risk"
        assert checkin.checkin_id
        assert checkin.notes

    def test_list_checkins(self, svc: OKRService):
        obj = svc.create_objective(org_id="org1", title="Goal", level="company", owner="ceo", period="2026-Q1")
        svc.add_checkin(objective_id=obj.obj_id, notes="All good", author="alice", status="on_track", confidence=0.8)
        svc.add_checkin(objective_id=obj.obj_id, notes="Some issues", author="bob", status="at_risk", confidence=0.5)
        checkins = svc.list_checkins(obj.obj_id)
        assert len(checkins) >= 2
        authors = [c.author for c in checkins]
        assert "alice" in authors and "bob" in authors
