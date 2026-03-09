from pathlib import Path

from packages.agents.registry import AgentRegistry
from packages.common.models import ChatRequest
from packages.governance.approvals import ApprovalService
from packages.governance.audit import AuditLog
from packages.governance.policy import PolicyEngine
from packages.memory.service import LayeredMemoryService
from packages.tools.policy_wrapped_tools import ToolExecutor
from workers.orchestrator.runtime import FridayManager


def _manager_with_temp_db(tmp_path: Path) -> FridayManager:
    root = Path(__file__).resolve().parents[1]
    registry = AgentRegistry(manifests_dir=root / "packages" / "agents" / "manifests")
    memory = LayeredMemoryService.with_sqlite(tmp_path / "memory.sqlite3")
    return FridayManager(
        registry=registry,
        memory=memory,
        policy=PolicyEngine(),
        approvals=ApprovalService(),
        audit=AuditLog(),
        tool_executor=ToolExecutor(root),
    )


def test_memory_candidates_can_be_promoted_with_approval(tmp_path: Path) -> None:
    manager = _manager_with_temp_db(tmp_path)
    response = manager.run(
        ChatRequest(
            user_id="u1",
            org_id="o1",
            conversation_id="c1",
            message="Please propose a new agent for procurement analytics",
            context_packet={},
        )
    )

    candidates = response["memory_candidates"]
    proposal = [c for c in candidates if c["candidate_type"] == "prompt_improvement_proposal"][0]

    promote_without_approval = manager._memory.promote_candidate(proposal["candidate_id"], approved=False)
    assert promote_without_approval["status"] == "approval_required"

    promote_with_approval = manager._memory.promote_candidate(proposal["candidate_id"], approved=True)
    assert promote_with_approval["status"] == "promoted"


def test_research_requests_include_web_research_tool_call(tmp_path: Path) -> None:
    manager = _manager_with_temp_db(tmp_path)
    response = manager.run(
        ChatRequest(
            user_id="u2",
            org_id="o1",
            conversation_id="c2",
            message="Research competitor pricing benchmarks for 2026",
            context_packet={},
        )
    )

    assert "web.research" in response["planner"]["required_tools"]
    executed_tools = [call["tool"] for call in response["tool_calls"]]
    assert "web.research" in executed_tools


def test_semantic_memory_persists_across_instances(tmp_path: Path) -> None:
    manager_a = _manager_with_temp_db(tmp_path)
    response = manager_a.run(
        ChatRequest(
            user_id="u3",
            org_id="o2",
            conversation_id="c9",
            message="Help with planning",
            context_packet={"communication_preference": "concise"},
        )
    )
    pref_candidate = [c for c in response["memory_candidates"] if c["candidate_type"] == "user_preference"][0]
    promoted = manager_a._memory.promote_candidate(pref_candidate["candidate_id"], approved=True)
    assert promoted["status"] == "promoted"

    manager_b = _manager_with_temp_db(tmp_path)
    search = manager_b._memory.search("o2", "concise")
    assert "communication_preference" in search["semantic_hits"]


def test_specialist_memos_include_shared_registry_governance_rules(tmp_path: Path) -> None:
    manager = _manager_with_temp_db(tmp_path)
    response = manager.run(
        ChatRequest(
            user_id="u-shared-rules",
            org_id="o-shared-rules",
            conversation_id="c-shared-rules",
            message="Build a business case for AI in sales operations",
            context_packet={},
        )
    )

    memos = response["specialist_memos"]
    assert memos, "Expected at least one specialist memo."
    for memo in memos:
        assert memo["confidence"] is not None
        assert any("Registry rule:" in item for item in memo["evidence"])
        assert any("read-only advisory mode" in item.lower() for item in memo["assumptions"])
        assert any("escalation note:" in item.lower() for item in memo["risks"])


from apps.api.service import FridayService
from packages.common.models import ChatRequest


def test_business_case_response_has_draft_and_questions() -> None:
    service = FridayService()
    response = service.manager.run(
        ChatRequest(
            user_id="u-biz",
            org_id="o-biz",
            conversation_id="c-biz",
            message="Create a business case for AI in sales",
            context_packet={},
        )
    )
    answer = response["final_answer"]["direct_answer"].lower()
    assert "draft business case" in answer
    assert "questions i need from you" in answer


def test_template_response_includes_fill_in_sections() -> None:
    service = FridayService()
    response = service.manager.run(
        ChatRequest(
            user_id="u-temp",
            org_id="o-temp",
            conversation_id="c-temp",
            message="Give me a template business case",
            context_packet={},
        )
    )
    answer = response["final_answer"]["direct_answer"].lower()
    assert "business case template" in answer
    assert "financial model" in answer


def test_generic_response_does_not_quote_prompt_verbatim() -> None:
    service = FridayService()
    prompt = "Help me come up with the executable plan"
    response = service.manager.run(
        ChatRequest(
            user_id="u-generic",
            org_id="o-generic",
            conversation_id="c-generic",
            message=prompt,
            context_packet={},
        )
    )
    answer = response["final_answer"]["direct_answer"].lower()
    assert "for this request ('" not in answer
    assert prompt.lower() not in answer


def test_project_charter_request_returns_charter_draft() -> None:
    service = FridayService()
    response = service.manager.run(
        ChatRequest(
            user_id="u-charter",
            org_id="o-charter",
            conversation_id="c-charter",
            message="I need to create a project charter for AI in project management",
            context_packet={},
        )
    )
    answer = response["final_answer"]["direct_answer"].lower()
    assert "before i draft the charter" in answer
    assert "answer these first" in answer


def test_project_charter_asks_foundational_ai_use_case_questions_first() -> None:
    service = FridayService()
    response = service.manager.run(
        ChatRequest(
            user_id="u-charter2",
            org_id="o-charter2",
            conversation_id="c-charter2",
            message="I need to write a project charter about implementing AI in project management",
            context_packet={},
        )
    )
    questions = [q.lower() for q in response["planner"]["missing_information"]]
    assert any("workflow should ai support first" in q for q in questions)
    assert any("problem is most urgent" in q for q in questions)
    assert any("charter audience and decision-maker" in q for q in questions)
    assert not any("timeline or decision deadline" in q for q in questions)
    assert not any("which kpi matters most" in q for q in questions)


def test_follow_up_message_uses_thread_context() -> None:
    service = FridayService()
    conv = "c-followup"
    service.manager.run(
        ChatRequest(
            user_id="u-followup",
            org_id="o-followup",
            conversation_id=conv,
            message="I need to create a project charter for using AI in project management",
            context_packet={},
        )
    )
    follow_up = service.manager.run(
        ChatRequest(
            user_id="u-followup",
            org_id="o-followup",
            conversation_id=conv,
            message="help me create it",
            context_packet={},
        )
    )
    answer = follow_up["final_answer"]["direct_answer"].lower()
    assert "draft the charter" in answer


def test_project_charter_with_enough_inputs_returns_draft() -> None:
    service = FridayService()
    response = service.manager.run(
        ChatRequest(
            user_id="u-charter-full",
            org_id="o-charter-full",
            conversation_id="c-charter-full",
            message=(
                "Create a project charter for AI in project management. "
                "The first workflow is status reporting. "
                "Main problem is manual rework and delays. "
                "Audience is the steering committee sponsor. "
                "Decision deadline is Q3 kickoff. "
                "Primary metric is cycle time reduction."
            ),
            context_packet={},
        )
    )
    answer = response["final_answer"]["direct_answer"].lower()
    assert "project charter v1" in answer
    assert "success metrics" in answer
