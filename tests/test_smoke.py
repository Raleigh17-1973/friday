from business_ai.app import build_orchestrator
from business_ai.core.models import TaskRequest


def test_project_risk_routes_to_pmo() -> None:
    orch = build_orchestrator()
    result = orch.run(TaskRequest(text="How do I write a project risk?", project_id="p1", conversation_id="c1"))
    assert result.domain == "pmo"


def test_finance_question_routes_to_finance() -> None:
    orch = build_orchestrator()
    result = orch.run(TaskRequest(text="What finance assumptions should I make?", project_id="p1", conversation_id="c1"))
    assert result.domain == "finance"


def test_status_email_routes_to_communications() -> None:
    orch = build_orchestrator()
    result = orch.run(TaskRequest(text="How do I write a project status email?", project_id="p1", conversation_id="c1"))
    assert result.domain == "communications"
