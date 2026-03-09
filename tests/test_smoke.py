from pathlib import Path

from apps.api.service import FridayService
from packages.common.models import ChatRequest


def test_manager_orchestrates_required_specialists() -> None:
    service = FridayService()
    response = service.manager.run(
        ChatRequest(
            user_id="u1",
            org_id="o1",
            conversation_id="c1",
            message="Need ROI and process bottleneck plan with explicit risks",
            context_packet={},
        )
    )

    consulted = set(response["final_answer"]["experts_consulted"])
    assert "chief_of_staff_strategist" in consulted
    assert "finance" in consulted
    assert "operations" in consulted
    assert "critic_red_team" in consulted


def test_write_scope_triggers_approval_gate() -> None:
    service = FridayService()
    response = service.manager.run(
        ChatRequest(
            user_id="u2",
            org_id="o1",
            conversation_id="c2",
            message="Update CRM with this new pricing plan",
            context_packet={"requested_write_scopes": ["crm.write"]},
        )
    )
    assert response["approval"] is not None
    assert response["approval"]["status"] == "pending"


def test_agent_manifests_include_agent_architect() -> None:
    path = Path("packages/agents/manifests/agent_architect.json")
    assert path.exists()


def test_project_management_requests_consult_project_manager() -> None:
    service = FridayService()
    response = service.manager.run(
        ChatRequest(
            user_id="u3",
            org_id="o1",
            conversation_id="c3",
            message="Create a project charter and RAID governance plan for this initiative",
            context_packet={},
        )
    )
    consulted = set(response["final_answer"]["experts_consulted"])
    assert "project_manager" in consulted
