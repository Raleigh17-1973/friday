from pathlib import Path

from packages.common.models import (
    CriticReport,
    FinalAnswerPackage,
    PlannerOutput,
    RiskLevel,
    RunTrace,
    SpecialistMemo,
)
from packages.governance.audit import AuditLog
from packages.governance.run_store import SQLiteRunStore


def _sample_trace(run_id: str = "run_test") -> RunTrace:
    return RunTrace(
        run_id=run_id,
        org_id="org-1",
        user_id="user-1",
        conversation_id="conv-1",
        planner=PlannerOutput(
            problem_statement="Test",
            missing_information=[],
            domains_involved=["finance"],
            recommended_specialists=["finance"],
            required_tools=["docs.retrieve"],
            risk_level=RiskLevel.LOW,
            output_format="executive_brief",
        ),
        selected_agents=["finance"],
        tool_calls=[{"tool": "docs.retrieve", "mode": "read_only"}],
        specialist_memos=[
            SpecialistMemo(
                specialist_id="finance",
                analysis="a",
                recommendation="b",
                assumptions=[],
                risks=[],
                evidence=[],
                confidence=0.5,
                questions=[],
            )
        ],
        critic_report=CriticReport(
            blind_spots=[],
            challenged_assumptions=[],
            alternative_path="alt",
            residual_risks=[],
        ),
        final_answer=FinalAnswerPackage(
            direct_answer="x",
            executive_summary="y",
            key_assumptions=[],
            major_risks=[],
            recommended_next_steps=["n1"],
        ),
        confidence=0.5,
        feedback={},
        outcome={},
    )


def test_audit_log_persists_and_reloads_from_sqlite_store(tmp_path: Path) -> None:
    store = SQLiteRunStore(tmp_path / "audit.sqlite3")

    log_a = AuditLog(run_store=store)
    trace = _sample_trace("run_123")
    log_a.record_run(trace)
    log_a.append_event("run_123", {"type": "custom", "message": "ok"})

    log_b = AuditLog(run_store=store)
    loaded = log_b.get_run("run_123")
    assert loaded is not None
    assert loaded.run_id == "run_123"
    events = log_b.get_events("run_123")
    assert len(events) >= 2
