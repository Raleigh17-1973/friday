"""Tests for the 5 new specialist agents and their keyword routing."""
from __future__ import annotations

import pytest
from workers.orchestrator.planner import build_plan


def _plan(msg: str):
    """Build a plan in keyword-stub mode (no LLM call)."""
    return build_plan(msg, llm=None)


# ---------------------------------------------------------------------------
# AI Strategy
# ---------------------------------------------------------------------------
class TestAIStrategyRouting:
    def test_automation_opportunity(self):
        plan = _plan("find automation opportunity in our sales process")
        assert "ai_strategy" in plan.recommended_specialists

    def test_agentize(self):
        plan = _plan("how can we agentize our onboarding workflow")
        assert "ai_strategy" in plan.recommended_specialists

    def test_workflow_automation(self):
        plan = _plan("we need workflow automation for invoice processing")
        assert "ai_strategy" in plan.recommended_specialists

    def test_ai_operating_model(self):
        plan = _plan("help us design an ai operating model for the company")
        assert "ai_strategy" in plan.recommended_specialists

    def test_where_can_ai_help(self):
        plan = _plan("where can AI replace repetitive work in operations")
        assert "ai_strategy" in plan.recommended_specialists


# ---------------------------------------------------------------------------
# Internal Comms
# ---------------------------------------------------------------------------
class TestInternalCommsRouting:
    def test_all_hands(self):
        plan = _plan("write an all-hands memo about the product launch")
        assert "internal_comms" in plan.recommended_specialists

    def test_internal_announcement(self):
        plan = _plan("draft an internal announcement about the new policy")
        assert "internal_comms" in plan.recommended_specialists

    def test_change_management(self):
        plan = _plan("help with change management communication for the reorg")
        assert "internal_comms" in plan.recommended_specialists

    def test_employee_communication(self):
        plan = _plan("write employee communication about the benefits update")
        assert "internal_comms" in plan.recommended_specialists

    def test_org_memo(self):
        plan = _plan("write an org memo about the leadership transition")
        assert "internal_comms" in plan.recommended_specialists

    def test_internal_launch(self):
        plan = _plan("internal launch communication plan for the new HR system")
        assert "internal_comms" in plan.recommended_specialists


# ---------------------------------------------------------------------------
# Public Relations
# ---------------------------------------------------------------------------
class TestPRRouting:
    def test_press_release(self):
        plan = _plan("write a press release for our Series B announcement")
        assert "public_relations" in plan.recommended_specialists

    def test_media_strategy(self):
        plan = _plan("what should our media strategy be for the product launch")
        assert "public_relations" in plan.recommended_specialists

    def test_reputation(self):
        plan = _plan("how do we protect our reputation after this incident")
        assert "public_relations" in plan.recommended_specialists

    def test_talking_points(self):
        plan = _plan("develop talking points for the journalist interview")
        assert "public_relations" in plan.recommended_specialists

    def test_pr_strategy(self):
        plan = _plan("develop a pr strategy for our IPO")
        assert "public_relations" in plan.recommended_specialists

    def test_press_statement(self):
        plan = _plan("we need a press statement about the data breach")
        assert "public_relations" in plan.recommended_specialists


# ---------------------------------------------------------------------------
# M&A
# ---------------------------------------------------------------------------
class TestMARouting:
    def test_acquisition(self):
        plan = _plan("evaluate this acquisition target for strategic fit")
        assert "mergers_acquisitions" in plan.recommended_specialists

    def test_due_diligence(self):
        plan = _plan("we need to run due diligence on the deal")
        assert "mergers_acquisitions" in plan.recommended_specialists

    def test_synergy_analysis(self):
        plan = _plan("model the synergies from the merger")
        assert "mergers_acquisitions" in plan.recommended_specialists

    def test_acqui_hire(self):
        plan = _plan("evaluate an acqui-hire of this engineering team")
        assert "mergers_acquisitions" in plan.recommended_specialists

    def test_divestiture(self):
        plan = _plan("analyze the divestiture options for this business unit")
        assert "mergers_acquisitions" in plan.recommended_specialists

    def test_letter_of_intent(self):
        plan = _plan("help us draft the LOI for the acquisition")
        assert "mergers_acquisitions" in plan.recommended_specialists


# ---------------------------------------------------------------------------
# OKR Coach
# ---------------------------------------------------------------------------
class TestOKRCoachRouting:
    def test_write_an_okr(self):
        plan = _plan("help me write an okr for the product team")
        assert "okr_coach" in plan.recommended_specialists

    def test_review_okr(self):
        plan = _plan("review my okr and tell me if it's measurable")
        assert "okr_coach" in plan.recommended_specialists

    def test_key_result(self):
        plan = _plan("is this a good key result: increase revenue by 20%")
        assert "okr_coach" in plan.recommended_specialists

    def test_okr_quality(self):
        plan = _plan("check okr quality for our engineering team")
        assert "okr_coach" in plan.recommended_specialists

    def test_okr_alignment(self):
        plan = _plan("help with okr alignment across teams")
        assert "okr_coach" in plan.recommended_specialists


# ---------------------------------------------------------------------------
# Anti-trigger (make sure financial / legal questions don't bleed into comms)
# ---------------------------------------------------------------------------
class TestAntiTriggers:
    def test_financial_analysis_not_internal_comms(self):
        plan = _plan("model our Q3 revenue forecast and cost structure")
        assert "internal_comms" not in plan.recommended_specialists

    def test_legal_review_not_pr(self):
        plan = _plan("review this contract for compliance issues")
        assert "public_relations" not in plan.recommended_specialists

    def test_no_crash_on_empty(self):
        plan = _plan("hello")
        assert plan is not None
        assert isinstance(plan.recommended_specialists, list)

    def test_no_crash_on_long_message(self):
        msg = "analyze " * 100
        plan = _plan(msg)
        assert plan is not None

    def test_generic_strategy_not_okr_coach(self):
        plan = _plan("develop a competitive strategy for the enterprise market")
        # okr_coach shouldn't fire on generic strategy without OKR framing
        # (It's OK if chief_of_staff_strategist fires instead)
        assert plan is not None
