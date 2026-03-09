from pathlib import Path

from apps.api.service import FridayService
from packages.common.models import ChatRequest
from workers.evals.harness import EvalHarness
from workers.orchestrator.workflows import InProcessWorkflowEngine


def test_workflow_engine_runs_and_persists(tmp_path: Path) -> None:
    engine = InProcessWorkflowEngine(tmp_path / "wf.sqlite3")

    def execute(payload: dict) -> dict:
        return {"echo": payload["value"]}

    record = engine.run({"value": 42}, execute)
    assert record.status == "completed"

    fetched = engine.get(record.workflow_id)
    assert fetched is not None
    assert fetched.result == {"echo": 42}


def test_eval_harness_scores_core_routing() -> None:
    service = FridayService()
    harness = EvalHarness(Path(__file__).resolve().parents[1])
    report = harness.run_suite("core-routing", service.manager)

    assert report.total >= 1
    assert 0.0 <= report.avg_score <= 1.0


def test_reflection_report_is_added_to_chat_result() -> None:
    service = FridayService()
    payload = ChatRequest(
        user_id="u3",
        org_id="o3",
        conversation_id="c3",
        message="Need finance and operations options with risks",
        context_packet={},
    )
    result = service.manager.run(payload)
    trace = service.audit.get_run(result["run_id"])
    assert trace is not None

    reflection = service.reflection.reflect(trace, service.memory)
    assert 0.0 <= reflection.score <= 1.0
    assert reflection.candidate_ids
