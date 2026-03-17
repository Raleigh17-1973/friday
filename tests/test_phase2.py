from pathlib import Path
import sqlite3

from packages.agents.registry import AgentRegistry
from packages.common.models import ApprovalRequest, ChatRequest
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


def test_approval_service_loads_legacy_sqlite_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "approvals.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE approvals ("
        "approval_id TEXT PRIMARY KEY, "
        "run_id TEXT, "
        "reason TEXT, "
        "action_summary TEXT, "
        "requested_scopes TEXT, "
        "created_at TEXT, "
        "status TEXT, "
        "assignee TEXT)"
    )
    conn.execute(
        "INSERT INTO approvals (approval_id, run_id, reason, action_summary, requested_scopes, created_at, status, assignee) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "appr-legacy",
            "run-legacy",
            "legacy reason",
            "legacy action",
            '["crm.write"]',
            "2026-03-17T00:00:00Z",
            "pending",
            "reviewer-1",
        ),
    )
    conn.commit()
    conn.close()

    service = ApprovalService(db_path=db_path)

    approval = service.get("appr-legacy")
    assert approval.run_id == "run-legacy"
    assert approval.requested_scopes == ["crm.write"]
    assert approval.assignee == "reviewer-1"

    check = sqlite3.connect(db_path)
    data = check.execute(
        "SELECT data FROM approvals WHERE approval_id = ?",
        ("appr-legacy",),
    ).fetchone()[0]
    check.close()
    assert "legacy action" in data


def test_approval_service_creates_fresh_sqlite_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "approvals.sqlite3"
    service = ApprovalService(db_path=db_path)
    service.create(
        ApprovalRequest(
            approval_id="appr-fresh",
            run_id="run-fresh",
            reason="need approval",
            action_summary="approve this write",
            requested_scopes=["crm.write"],
        )
    )

    reloaded = ApprovalService(db_path=db_path)
    approval = reloaded.get("appr-fresh")
    assert approval.status == "pending"
    assert approval.requested_scopes == ["crm.write"]


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


def test_business_case_response_has_draft_and_pilot_plan() -> None:
    """Business case stub should produce a draft with a financial model and pilot plan."""
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
    # Stub now produces a financial model and pilot plan instead of raw questions
    assert any(kw in answer for kw in ("financial model", "pilot plan", "recommendation"))


def test_template_response_includes_fill_in_sections() -> None:
    """Template request should produce a business case draft with financial model."""
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
    # Stub routes template requests to the draft business case path
    assert any(kw in answer for kw in ("business case template", "draft business case"))
    assert "financial model" in answer


def test_generic_response_does_not_use_legacy_stub_wrapper() -> None:
    """Generic responses should not use the old 'for this request (...)' wrapper format."""
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
    # Stub should not use old wrapper format
    assert "for this request ('" not in answer
    # Stub should produce structured guidance, not just echo the prompt
    assert any(kw in answer for kw in ("recommended next steps", "analysis", "recommendation"))


def test_project_charter_request_returns_discovery_questions() -> None:
    """Thin charter request (no workflow/problem/audience specified) should return discovery questions."""
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
    # Stub should surface discovery questions before drafting
    assert "before i draft" in answer
    assert any(kw in answer for kw in ("workflow", "problem", "audience", "specific"))


def test_project_charter_asks_foundational_questions_first() -> None:
    """Planner should surface workflow, problem, and audience questions before timeline/KPI questions."""
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
    # Planner must surface at least 2 foundational discovery questions before proceeding
    foundational_hits = sum([
        any("workflow" in q and "ai" in q for q in questions),
        any("problem" in q or "urgent" in q for q in questions),
        any("audience" in q or "decision-maker" in q for q in questions),
    ])
    assert foundational_hits >= 2, f"Expected ≥2 foundational questions, got: {questions}"


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
    # Follow-up should include the original charter context and surface discovery questions
    assert any(kw in answer for kw in ("charter", "project charter", "draft"))


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
    # Full inputs should produce a complete charter draft (not just discovery questions)
    assert "project charter" in answer
    assert "success metrics" in answer
