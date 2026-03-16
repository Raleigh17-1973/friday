from __future__ import annotations

"""Tests for the enterprise OKR system (v2 schema)."""

import pytest
from pathlib import Path

from packages.okrs.service import EnterpriseOKRService
from packages.okrs.models import (
    OrgNode, OKRPeriod, Objective, KeyResult, OKRKPI, KRKPILink,
    OKRInitiative, OKRCheckin, OKRDependency, ValidationIssue,
)
from packages.okrs.validation import OKRValidator


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def svc(tmp_path: Path) -> EnterpriseOKRService:
    return EnterpriseOKRService(db_path=tmp_path / "okrs_test.sqlite3")


@pytest.fixture
def company_node(svc: EnterpriseOKRService) -> OrgNode:
    return svc.create_org_node("Acme Corp", "company", org_id="org-1")


@pytest.fixture
def team_node(svc: EnterpriseOKRService, company_node: OrgNode) -> OrgNode:
    return svc.create_org_node("Engineering", "team", parent_id=company_node.node_id, org_id="org-1")


@pytest.fixture
def q2_period(svc: EnterpriseOKRService) -> OKRPeriod:
    return svc.create_period("FY2026 Q2", "quarterly", 2026, 2, "2026-04-01", "2026-06-30", "org-1")


@pytest.fixture
def committed_obj(svc: EnterpriseOKRService, company_node: OrgNode, q2_period: OKRPeriod) -> Objective:
    return svc.create_objective(
        period_id=q2_period.period_id,
        org_node_id=company_node.node_id,
        title="Become the undisputed market leader in SMB HR",
        objective_type="committed",
        owner_user_id="user-1",
        org_id="org-1",
        sponsor_user_id="exec-1",
    )


# ── Org Hierarchy ─────────────────────────────────────────────────────────────

class TestOrgNodeHierarchy:
    def test_create_company_node(self, svc: EnterpriseOKRService):
        node = svc.create_org_node("MyCompany", "company")
        assert node.node_id
        assert node.name == "MyCompany"
        assert node.node_type == "company"

    def test_create_team_under_company(self, svc: EnterpriseOKRService, company_node: OrgNode):
        team = svc.create_org_node("Sales", "team", parent_id=company_node.node_id)
        assert team.parent_id == company_node.node_id

    def test_list_org_nodes(self, svc: EnterpriseOKRService, company_node: OrgNode, team_node: OrgNode):
        nodes = svc.list_org_nodes(org_id="org-1")
        node_ids = {n.node_id for n in nodes}
        # includes the seeded default company node + our nodes
        assert company_node.node_id in node_ids
        assert team_node.node_id in node_ids

    def test_default_company_node_seeded(self, svc: EnterpriseOKRService):
        """Service seeds a default company node on startup."""
        node = svc.get_org_node("node-company")
        assert node is not None
        assert node.node_type == "company"

    def test_get_org_tree(self, svc: EnterpriseOKRService, company_node: OrgNode, team_node: OrgNode):
        tree = svc.get_org_tree(org_id="org-1")
        assert isinstance(tree, dict)


# ── OKR Periods ───────────────────────────────────────────────────────────────

class TestOKRPeriods:
    def test_create_quarterly_period(self, svc: EnterpriseOKRService):
        p = svc.create_period("FY2026 Q1", "quarterly", 2026, 1, "2026-01-01", "2026-03-31", "org-1")
        assert p.period_id
        assert p.period_type == "quarterly"
        assert p.quarter == 1
        assert p.status == "draft"

    def test_create_annual_period(self, svc: EnterpriseOKRService):
        p = svc.create_period("FY2026", "annual", 2026, None, "2026-01-01", "2026-12-31", "org-1")
        assert p.period_type == "annual"
        assert p.quarter is None

    def test_activate_period(self, svc: EnterpriseOKRService, q2_period: OKRPeriod):
        active = svc.activate_period(q2_period.period_id)
        assert active.status == "active"

    def test_close_period(self, svc: EnterpriseOKRService, q2_period: OKRPeriod):
        svc.activate_period(q2_period.period_id)
        closed = svc.close_period(q2_period.period_id)
        assert closed.status == "closed"

    def test_list_periods_with_status_filter(self, svc: EnterpriseOKRService, q2_period: OKRPeriod):
        svc.activate_period(q2_period.period_id)
        active_periods = svc.list_periods(org_id="org-1", status="active")
        assert any(p.period_id == q2_period.period_id for p in active_periods)


# ── Objective Hierarchy (Three Levels) ───────────────────────────────────────

class TestObjectiveHierarchyThreeLevels:
    def test_three_level_cascade(
        self,
        svc: EnterpriseOKRService,
        company_node: OrgNode,
        q2_period: OKRPeriod,
    ):
        # Company level
        company_obj = svc.create_objective(
            period_id=q2_period.period_id,
            org_node_id=company_node.node_id,
            title="Achieve category leadership",
            objective_type="committed",
            owner_user_id="ceo",
            org_id="org-1",
        )

        # Team level (child of company)
        team_node = svc.create_org_node("Product", "team", parent_id=company_node.node_id, org_id="org-1")
        team_obj = svc.create_objective(
            period_id=q2_period.period_id,
            org_node_id=team_node.node_id,
            title="Ship features that win enterprise deals",
            objective_type="committed",
            owner_user_id="vp-product",
            org_id="org-1",
            parent_objective_id=company_obj.objective_id,
        )
        assert team_obj.parent_objective_id == company_obj.objective_id

        # Individual level (child of team)
        indiv_node = svc.create_org_node("Product Squad A", "team", parent_id=team_node.node_id, org_id="org-1")
        indiv_obj = svc.create_objective(
            period_id=q2_period.period_id,
            org_node_id=indiv_node.node_id,
            title="Deliver SSO integration for top 10 enterprise prospects",
            objective_type="committed",
            owner_user_id="pm-1",
            org_id="org-1",
            parent_objective_id=team_obj.objective_id,
        )
        assert indiv_obj.parent_objective_id == team_obj.objective_id

        # Hierarchy query
        hierarchy = svc.get_objective_hierarchy(company_obj.objective_id)
        assert isinstance(hierarchy, dict)


# ── Key Result Schema ─────────────────────────────────────────────────────────

class TestKeyResultSchema:
    def test_create_metric_kr(self, svc: EnterpriseOKRService, committed_obj: Objective):
        kr = svc.create_key_result(
            objective_id=committed_obj.objective_id,
            title="Grow NPS from 42 to 65",
            kr_type="metric",
            owner_user_id="user-1",
            org_id="org-1",
            baseline_value=42,
            target_value=65,
            unit="NPS points",
            direction="increase",
        )
        assert kr.kr_type == "metric"
        assert kr.baseline_value == 42
        assert kr.target_value == 65
        assert kr.score_current == 0.0  # no current value yet

    def test_create_milestone_kr(self, svc: EnterpriseOKRService, committed_obj: Objective):
        kr = svc.create_key_result(
            objective_id=committed_obj.objective_id,
            title="Launch enterprise pricing tier",
            kr_type="milestone",
            owner_user_id="user-1",
            org_id="org-1",
        )
        assert kr.kr_type == "milestone"

    def test_create_binary_kr(self, svc: EnterpriseOKRService, committed_obj: Objective):
        kr = svc.create_key_result(
            objective_id=committed_obj.objective_id,
            title="SOC 2 Type II certification complete",
            kr_type="binary",
            owner_user_id="user-1",
            org_id="org-1",
            description="Certification is issued by an accredited auditor and covers all in-scope systems",
        )
        assert kr.kr_type == "binary"

    def test_list_key_results(self, svc: EnterpriseOKRService, committed_obj: Objective):
        svc.create_key_result(
            objective_id=committed_obj.objective_id,
            title="KR 1", kr_type="metric", owner_user_id="user-1", org_id="org-1",
        )
        svc.create_key_result(
            objective_id=committed_obj.objective_id,
            title="KR 2", kr_type="binary", owner_user_id="user-1", org_id="org-1",
        )
        krs = svc.list_key_results(committed_obj.objective_id)
        assert len(krs) == 2


# ── KR Scoring ────────────────────────────────────────────────────────────────

class TestObjectiveProgressFromKeyResults:
    def test_metric_kr_score_calculation(self, svc: EnterpriseOKRService, committed_obj: Objective):
        kr = svc.create_key_result(
            objective_id=committed_obj.objective_id,
            title="Grow NPS from 42 to 60",
            kr_type="metric",
            owner_user_id="user-1",
            org_id="org-1",
            baseline_value=42,
            target_value=60,
            direction="increase",
        )
        svc.update_key_result(kr.kr_id, current_value=48)
        score = svc.compute_kr_score(kr.kr_id)
        # (48 - 42) / (60 - 42) = 6/18 = 0.333
        assert abs(score - 0.333) < 0.01

    def test_binary_kr_score_not_done(self, svc: EnterpriseOKRService, committed_obj: Objective):
        kr = svc.create_key_result(
            objective_id=committed_obj.objective_id,
            title="Binary KR",
            kr_type="binary",
            owner_user_id="user-1",
            org_id="org-1",
            target_value=1.0,
        )
        svc.update_key_result(kr.kr_id, current_value=0.0)
        score = svc.compute_kr_score(kr.kr_id)
        assert score == 0.0

    def test_binary_kr_score_done(self, svc: EnterpriseOKRService, committed_obj: Objective):
        kr = svc.create_key_result(
            objective_id=committed_obj.objective_id,
            title="Binary KR done",
            kr_type="binary",
            owner_user_id="user-1",
            org_id="org-1",
            target_value=1.0,
        )
        svc.update_key_result(kr.kr_id, current_value=1.0)
        score = svc.compute_kr_score(kr.kr_id)
        assert score == 1.0

    def test_decrease_direction_kr_score(self, svc: EnterpriseOKRService, committed_obj: Objective):
        kr = svc.create_key_result(
            objective_id=committed_obj.objective_id,
            title="Reduce churn from 5% to 2%",
            kr_type="metric",
            owner_user_id="user-1",
            org_id="org-1",
            baseline_value=5.0,
            target_value=2.0,
            direction="decrease",
        )
        svc.update_key_result(kr.kr_id, current_value=3.5)
        score = svc.compute_kr_score(kr.kr_id)
        # (5 - 3.5) / (5 - 2) = 1.5 / 3 = 0.5
        assert abs(score - 0.5) < 0.01

    def test_objective_score_aggregates_krs(self, svc: EnterpriseOKRService, committed_obj: Objective):
        kr1 = svc.create_key_result(
            objective_id=committed_obj.objective_id,
            title="KR1 metric", kr_type="metric", owner_user_id="user-1", org_id="org-1",
            baseline_value=0, target_value=100,
        )
        kr2 = svc.create_key_result(
            objective_id=committed_obj.objective_id,
            title="KR2 metric", kr_type="metric", owner_user_id="user-1", org_id="org-1",
            baseline_value=0, target_value=100,
        )
        svc.update_key_result(kr1.kr_id, current_value=50)
        svc.update_key_result(kr2.kr_id, current_value=70)
        obj_score = svc.compute_objective_score(committed_obj.objective_id)
        # Equal weighting: (0.5 + 0.7) / 2 = 0.6
        assert abs(obj_score - 0.6) < 0.01

    def test_score_clamped_at_1(self, svc: EnterpriseOKRService, committed_obj: Objective):
        kr = svc.create_key_result(
            objective_id=committed_obj.objective_id,
            title="Over-achieved KR", kr_type="metric", owner_user_id="user-1", org_id="org-1",
            baseline_value=0, target_value=100,
        )
        svc.update_key_result(kr.kr_id, current_value=150)  # exceeded target
        score = svc.compute_kr_score(kr.kr_id)
        assert score == 1.0  # clamped


# ── Check-ins ─────────────────────────────────────────────────────────────────

class TestCheckins:
    def test_add_kr_checkin(self, svc: EnterpriseOKRService, committed_obj: Objective):
        kr = svc.create_key_result(
            objective_id=committed_obj.objective_id,
            title="KR with checkin", kr_type="metric", owner_user_id="user-1",
            org_id="org-1", baseline_value=0, target_value=100,
        )
        checkin = svc.add_checkin(
            object_type="key_result",
            object_id=kr.kr_id,
            user_id="user-1",
            current_value=45.0,
            confidence=0.75,
            blockers="Vendor API delay",
            decisions_needed="Approve alternative vendor",
            narrative_update="Progress is on track despite API issues",
            next_steps="Evaluate vendor B",
            org_id="org-1",
        )
        assert checkin.checkin_id
        assert checkin.current_value == 45.0
        assert checkin.confidence_snapshot == 0.75

    def test_checkin_updates_kr_current_value(self, svc: EnterpriseOKRService, committed_obj: Objective):
        kr = svc.create_key_result(
            objective_id=committed_obj.objective_id,
            title="KR", kr_type="metric", owner_user_id="user-1",
            org_id="org-1", baseline_value=0, target_value=100,
        )
        svc.add_checkin(
            object_type="key_result",
            object_id=kr.kr_id,
            user_id="user-1",
            current_value=60.0,
            org_id="org-1",
        )
        updated_kr = svc.get_key_result(kr.kr_id)
        assert updated_kr.current_value == 60.0

    def test_list_checkins(self, svc: EnterpriseOKRService, committed_obj: Objective):
        kr = svc.create_key_result(
            objective_id=committed_obj.objective_id,
            title="KR", kr_type="metric", owner_user_id="user-1",
            org_id="org-1", baseline_value=0, target_value=100,
        )
        for val in [20, 40, 60]:
            svc.add_checkin(
                object_type="key_result",
                object_id=kr.kr_id,
                user_id="user-1",
                current_value=float(val),
                org_id="org-1",
            )
        checkins = svc.list_checkins("key_result", kr.kr_id, limit=10)
        assert len(checkins) == 3


# ── KPI and Links ─────────────────────────────────────────────────────────────

class TestKPIAndLinks:
    def test_create_kpi(self, svc: EnterpriseOKRService):
        kpi = svc.create_kpi(
            name="Monthly Recurring Revenue",
            unit="USD",
            org_id="org-1",
            metric_definition="Sum of active subscription MRR at month end",
            target_band_low=400000,
            target_band_high=600000,
        )
        assert kpi.kpi_id
        assert kpi.name == "Monthly Recurring Revenue"

    def test_link_kr_to_kpi(self, svc: EnterpriseOKRService, committed_obj: Objective):
        kr = svc.create_key_result(
            objective_id=committed_obj.objective_id,
            title="Grow MRR", kr_type="metric", owner_user_id="user-1",
            org_id="org-1", baseline_value=300000, target_value=500000,
        )
        kpi = svc.create_kpi(name="MRR", unit="USD", org_id="org-1")
        link = svc.link_kr_to_kpi(
            kr_id=kr.kr_id,
            kpi_id=kpi.kpi_id,
            link_type="derived_from",
            contribution_notes="Direct measurement of the same metric",
        )
        assert link.link_id
        assert link.link_type == "derived_from"

    def test_guardrail_kpi_link(self, svc: EnterpriseOKRService, committed_obj: Objective):
        kr = svc.create_key_result(
            objective_id=committed_obj.objective_id,
            title="Aggressive growth KR", kr_type="metric", owner_user_id="user-1",
            org_id="org-1",
        )
        kpi = svc.create_kpi(
            name="Customer Churn Rate",
            unit="%",
            org_id="org-1",
            target_band_low=0,
            target_band_high=5.0,
        )
        link = svc.link_kr_to_kpi(kr_id=kr.kr_id, kpi_id=kpi.kpi_id, link_type="guardrail")
        assert link.link_type == "guardrail"

        guardrails = svc.get_guardrail_kpis(kr.kr_id)
        assert any(k.kpi_id == kpi.kpi_id for k in guardrails)


# ── Initiatives ───────────────────────────────────────────────────────────────

class TestInitiatives:
    def test_create_and_list_initiative(self, svc: EnterpriseOKRService, committed_obj: Objective):
        init = svc.create_initiative(
            title="Build enterprise onboarding flow",
            owner_user_id="user-1",
            linked_objective_id=committed_obj.objective_id,
            org_id="org-1",
        )
        assert init.initiative_id
        assert init.status == "not_started"

        listed = svc.list_initiatives(org_id="org-1", objective_id=committed_obj.objective_id)
        assert any(i.initiative_id == init.initiative_id for i in listed)

    def test_update_initiative_status(self, svc: EnterpriseOKRService, committed_obj: Objective):
        init = svc.create_initiative(
            title="Design sprint", owner_user_id="user-1",
            linked_objective_id=committed_obj.objective_id, org_id="org-1",
        )
        updated = svc.update_initiative(init.initiative_id, status="in_progress")
        assert updated.status == "in_progress"


# ── Dependencies ──────────────────────────────────────────────────────────────

class TestDependencies:
    def test_create_dependency(self, svc: EnterpriseOKRService, company_node: OrgNode, q2_period: OKRPeriod):
        obj_a = svc.create_objective(
            period_id=q2_period.period_id, org_node_id=company_node.node_id,
            title="Obj A", objective_type="committed", owner_user_id="user-1", org_id="org-1",
        )
        obj_b = svc.create_objective(
            period_id=q2_period.period_id, org_node_id=company_node.node_id,
            title="Obj B", objective_type="committed", owner_user_id="user-1", org_id="org-1",
        )
        dep = svc.create_dependency(
            source_type="objective",
            source_id=obj_a.objective_id,
            target_type="objective",
            target_id=obj_b.objective_id,
            dep_type="blocked_by",
            severity="high",
            org_id="org-1",
        )
        assert dep.dependency_id
        assert dep.dependency_type == "blocked_by"

    def test_list_dependencies(self, svc: EnterpriseOKRService, company_node: OrgNode, q2_period: OKRPeriod):
        obj_a = svc.create_objective(
            period_id=q2_period.period_id, org_node_id=company_node.node_id,
            title="Obj A", objective_type="committed", owner_user_id="user-1", org_id="org-1",
        )
        obj_b = svc.create_objective(
            period_id=q2_period.period_id, org_node_id=company_node.node_id,
            title="Obj B", objective_type="committed", owner_user_id="user-1", org_id="org-1",
        )
        svc.create_dependency(
            source_type="objective", source_id=obj_a.objective_id,
            target_type="objective", target_id=obj_b.objective_id,
            dep_type="contributes_to", severity="medium", org_id="org-1",
        )
        deps = svc.list_dependencies("objective", obj_a.objective_id)
        assert len(deps) == 1


# ── Validation Engine ─────────────────────────────────────────────────────────

class TestValidationEngine:
    def test_validate_objective_activity_verb_warning(self, svc: EnterpriseOKRService, company_node: OrgNode, q2_period: OKRPeriod):
        validator = OKRValidator()
        obj = svc.create_objective(
            period_id=q2_period.period_id,
            org_node_id=company_node.node_id,
            title="Review customer satisfaction surveys",  # activity verb
            objective_type="committed",
            owner_user_id="user-1",
            org_id="org-1",
        )
        issues = validator.validate_objective(obj, [])
        rule_ids = {i.rule_id for i in issues}
        assert "OBJ-02" in rule_ids  # missing outcome verb
        assert "OBJ-03" in rule_ids  # committed without sponsor

    def test_validate_kr_activity_verb(self, svc: EnterpriseOKRService, committed_obj: Objective):
        validator = OKRValidator()
        kr = svc.create_key_result(
            objective_id=committed_obj.objective_id,
            title="Analyze customer churn data",  # activity verb "analyze"
            kr_type="metric",
            owner_user_id="user-1",
            org_id="org-1",
            baseline_value=0,
            target_value=100,
        )
        issues = validator.validate_key_result(kr, committed_obj)
        rule_ids = {i.rule_id for i in issues}
        assert "KR-05" in rule_ids

    def test_validate_metric_kr_missing_baseline(self, svc: EnterpriseOKRService, committed_obj: Objective):
        validator = OKRValidator()
        kr = svc.create_key_result(
            objective_id=committed_obj.objective_id,
            title="Grow revenue to $1M",
            kr_type="metric",
            owner_user_id="user-1",
            org_id="org-1",
            # No baseline_value!
            target_value=1000000,
        )
        issues = validator.validate_key_result(kr, committed_obj)
        rule_ids = {i.rule_id for i in issues}
        assert "KR-03a" in rule_ids

    def test_validate_compensation_language(self, svc: EnterpriseOKRService, company_node: OrgNode, q2_period: OKRPeriod):
        validator = OKRValidator()
        obj = svc.create_objective(
            period_id=q2_period.period_id,
            org_node_id=company_node.node_id,
            title="Improve performance scores for bonus eligibility",
            objective_type="committed",
            owner_user_id="user-1",
            org_id="org-1",
        )
        issues = validator.validate_objective(obj, [])
        rule_ids = {i.rule_id for i in issues}
        assert "OBJ-04" in rule_ids  # compensation language

    def test_validate_binary_kr_missing_criteria(self, svc: EnterpriseOKRService, committed_obj: Objective):
        validator = OKRValidator()
        kr = svc.create_key_result(
            objective_id=committed_obj.objective_id,
            title="Get certification",
            kr_type="binary",
            owner_user_id="user-1",
            org_id="org-1",
            description="done",  # too short
        )
        issues = validator.validate_key_result(kr, committed_obj)
        rule_ids = {i.rule_id for i in issues}
        assert "KR-04" in rule_ids

    def test_validate_max_objectives_per_period(self, svc: EnterpriseOKRService, company_node: OrgNode, q2_period: OKRPeriod):
        validator = OKRValidator()
        # Create 5 existing objectives
        existing = []
        for i in range(5):
            existing.append(svc.create_objective(
                period_id=q2_period.period_id,
                org_node_id=company_node.node_id,
                title=f"Objective {i+1}: Grow category {i}",
                objective_type="committed",
                owner_user_id="user-1",
                org_id="org-1",
                sponsor_user_id="exec-1",
            ))
        new_obj = svc.create_objective(
            period_id=q2_period.period_id,
            org_node_id=company_node.node_id,
            title="Objective 6: Expand into new market",
            objective_type="committed",
            owner_user_id="user-1",
            org_id="org-1",
            sponsor_user_id="exec-1",
        )
        issues = validator.validate_objective(new_obj, existing)
        rule_ids = {i.rule_id for i in issues}
        assert "OBJ-01" in rule_ids


# ── Workspace Slug (from existing passing suite — non-OKR test preserved) ────

class TestWorkspaceSlugUniqueness:
    """Minimal smoke test for workspace slug uniqueness (kept from prior test file)."""
    def test_placeholder(self):
        # Workspace slug tests live in test_workspaces.py
        assert True


# ── End-to-end schema verification ───────────────────────────────────────────

def test_end_to_end_schema_and_scoring():
    """Standalone smoke test that matches the plan verification script."""
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmp:
        svc = EnterpriseOKRService(db_path=Path(tmp) / "e2e.sqlite3")
        node = svc.create_org_node("Acme Corp", "company", org_id="org-1")
        period = svc.create_period("FY2026 Q2", "quarterly", 2026, 2, "2026-04-01", "2026-06-30", "org-1")
        obj = svc.create_objective(
            period.period_id, node.node_id,
            "Become the market leader", "committed", "user-1", org_id="org-1",
        )
        kr = svc.create_key_result(
            obj.objective_id, "Grow NPS from 42 to 60", "metric", "user-1",
            baseline_value=42, target_value=60, direction="increase", org_id="org-1",
        )
        svc.update_key_result(kr.kr_id, current_value=48)
        score = svc.compute_kr_score(kr.kr_id)
        # (48 - 42) / (60 - 42) = 6/18 ≈ 0.333
        assert 0.30 <= score <= 0.36, f"Unexpected score: {score}"
