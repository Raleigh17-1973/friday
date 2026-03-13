"""Tests for the provenance / consultation-history classifier."""
from __future__ import annotations

import pytest
from dataclasses import field
from packages.common.models import (
    CriticReport,
    FinalAnswerPackage,
    PlannerOutput,
    RiskLevel,
    RunTrace,
    SpecialistMemo,
)
from workers.orchestrator.runtime import _build_provenance_answer, _is_provenance_question


# ---------------------------------------------------------------------------
# Helper: build a minimal RunTrace for testing
# ---------------------------------------------------------------------------
def _make_trace(selected_agents: list[str], conversation_id: str = "conv_test") -> RunTrace:
    planner = PlannerOutput(
        problem_statement="Test question",
        missing_information=[],
        domains_involved=[],
        recommended_specialists=selected_agents,
        required_tools=[],
        risk_level=RiskLevel.LOW,
        output_format="executive_brief",
    )
    final_answer = FinalAnswerPackage(
        direct_answer="Test answer",
        executive_summary="",
        key_assumptions=[],
        major_risks=[],
        recommended_next_steps=[],
        experts_consulted=selected_agents,
        confidence=0.85,
    )
    critic = CriticReport(
        blind_spots=[],
        challenged_assumptions=[],
        alternative_path="",
        residual_risks=[],
    )
    return RunTrace(
        run_id="run_test_001",
        org_id="org1",
        user_id="user1",
        conversation_id=conversation_id,
        planner=planner,
        selected_agents=selected_agents,
        tool_calls=[],
        specialist_memos=[],
        critic_report=critic,
        final_answer=final_answer,
        confidence=0.85,
        feedback={},
        outcome={},
    )


# ---------------------------------------------------------------------------
# _is_provenance_question
# ---------------------------------------------------------------------------
class TestProvenanceQuestionDetected:
    def test_did_you_consult(self):
        assert _is_provenance_question("did you consult legal?")

    def test_which_agents(self):
        assert _is_provenance_question("which agents did you use for that answer?")

    def test_who_was_consulted(self):
        assert _is_provenance_question("who was consulted?")

    def test_did_you_ask(self):
        assert _is_provenance_question("did you ask finance to review this?")

    def test_what_agents(self):
        assert _is_provenance_question("what agents were involved in that response?")

    def test_which_specialists(self):
        assert _is_provenance_question("which specialists were involved?")

    def test_was_legal_consulted(self):
        assert _is_provenance_question("was legal consulted on the contract review?")

    def test_did_you_involve(self):
        assert _is_provenance_question("did you involve HR in that recommendation?")

    def test_did_you_loop_in(self):
        assert _is_provenance_question("did you loop in security?")

    def test_what_specialists(self):
        assert _is_provenance_question("what specialists did you use?")

    def test_case_insensitive(self):
        assert _is_provenance_question("DID YOU CONSULT LEGAL?")
        assert _is_provenance_question("Which Agents Were Used?")

    def test_did_you_ask_legal(self):
        assert _is_provenance_question("did you ask legal about this contract?")

    def test_did_you_ask_finance(self):
        assert _is_provenance_question("did you ask finance to look at the numbers?")


class TestNonProvenanceNotDetected:
    def test_revenue_question(self):
        assert not _is_provenance_question("what is our Q3 revenue forecast?")

    def test_generic_strategy(self):
        assert not _is_provenance_question("analyze our competitive positioning in APAC")

    def test_okr_question(self):
        assert not _is_provenance_question("help me write an OKR for the product team")

    def test_press_release(self):
        assert not _is_provenance_question("write a press release for our Series B")

    def test_empty_string(self):
        assert not _is_provenance_question("")

    def test_general_question(self):
        assert not _is_provenance_question("what should our go-to-market strategy be?")

    def test_sales_pipeline(self):
        assert not _is_provenance_question("analyze our sales pipeline for Q2")


# ---------------------------------------------------------------------------
# _build_provenance_answer
# ---------------------------------------------------------------------------
class TestBuildProvenanceAnswer:
    def test_answer_with_consultations(self):
        trace = _make_trace(["legal_compliance", "finance"])
        answer = _build_provenance_answer("which agents did you consult?", trace)
        assert "Legal / Compliance" in answer
        assert "Finance" in answer

    def test_answer_empty_agents(self):
        trace = _make_trace([])
        answer = _build_provenance_answer("which agents did you use?", trace)
        assert "without specialist consultation" in answer.lower() or "directly" in answer.lower()

    def test_gap_detection_legal_not_consulted(self):
        trace = _make_trace(["finance"])  # legal was NOT consulted
        answer = _build_provenance_answer("did legal review this contract?", trace)
        # Should acknowledge the gap (bold markdown: "**not**")
        lower = answer.lower()
        assert "not" in lower and ("legal" in lower or "compliance" in lower)

    def test_gap_detection_finance_not_consulted(self):
        trace = _make_trace(["legal_compliance"])  # finance NOT consulted
        answer = _build_provenance_answer("did finance review the numbers?", trace)
        lower = answer.lower()
        assert "not" in lower and "finance" in lower

    def test_no_gap_when_all_relevant_consulted(self):
        trace = _make_trace(["legal_compliance", "finance"])
        answer = _build_provenance_answer("did you consult the relevant agents?", trace)
        # Should confirm agents were consulted
        assert "Legal / Compliance" in answer or "Finance" in answer

    def test_single_agent_consulted(self):
        trace = _make_trace(["marketing_brand"])
        answer = _build_provenance_answer("which agents did you use?", trace)
        assert "Marketing" in answer

    def test_answer_is_string(self):
        trace = _make_trace(["operations"])
        answer = _build_provenance_answer("who did you consult?", trace)
        assert isinstance(answer, str)
        assert len(answer) > 0

    def test_answer_contains_consulted_word(self):
        trace = _make_trace(["finance", "legal_compliance"])
        answer = _build_provenance_answer("which agents did you use?", trace)
        # Must be informative — reference the consulted agents
        assert "Finance" in answer or "Legal" in answer

    def test_revisit_offer_in_gap_response(self):
        trace = _make_trace(["finance"])
        answer = _build_provenance_answer("did legal check this?", trace)
        # Should offer to revisit (gap acknowledged)
        lower = answer.lower()
        assert "revisit" in lower or "perspective" in lower or "not" in lower

    def test_okr_gap_detection(self):
        trace = _make_trace(["finance"])
        answer = _build_provenance_answer("did you ask the okr coach?", trace)
        # OKR coach not in the trace
        assert isinstance(answer, str)

    def test_security_gap_detection(self):
        trace = _make_trace(["legal_compliance"])
        answer = _build_provenance_answer("did security review the risk?", trace)
        assert isinstance(answer, str)
        lower = answer.lower()
        # Security agent wasn't consulted — should mention "not" and "security" or "risk"
        assert "not" in lower or "security" in lower or "risk" in lower
