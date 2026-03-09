from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from packages.common.models import ChatRequest


@dataclass
class EvalCaseResult:
    case_id: str
    passed: bool
    score: float
    notes: list[str]


@dataclass
class EvalReport:
    suite: str
    total: int
    passed: int
    avg_score: float
    cases: list[EvalCaseResult]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EvalHarness:
    def __init__(self, repo_root: Path) -> None:
        self._repo_root = repo_root

    def run_suite(self, suite: str, manager) -> EvalReport:
        scenario_file = self._repo_root / "evals" / "scenarios" / f"{suite}.json"
        if not scenario_file.exists():
            raise FileNotFoundError(f"Unknown eval suite: {suite}")

        scenarios = json.loads(scenario_file.read_text(encoding="utf-8"))
        results: list[EvalCaseResult] = []

        for scenario in scenarios:
            case_id = str(scenario["id"])
            req = ChatRequest(
                user_id="eval-user",
                org_id="eval-org",
                conversation_id=f"eval-{case_id}",
                message=str(scenario["message"]),
                context_packet={},
            )
            output = manager.run(req)
            final = output["final_answer"]
            experts = set(final.get("experts_consulted") or [])

            expected_experts = set(scenario.get("expected_experts") or [])
            missing_experts = sorted(expected_experts - experts)
            has_steps = bool(final.get("recommended_next_steps"))
            has_risks = bool(final.get("major_risks"))

            score = 0.0
            notes: list[str] = []
            if not missing_experts:
                score += 0.5
            else:
                notes.append(f"Missing experts: {', '.join(missing_experts)}")

            if has_steps:
                score += 0.25
            else:
                notes.append("Missing next steps")

            if has_risks:
                score += 0.25
            else:
                notes.append("Missing risks")

            passed = score >= 0.75
            if passed:
                notes.append("Pass")

            results.append(EvalCaseResult(case_id=case_id, passed=passed, score=score, notes=notes))

        total = len(results)
        passed_count = len([r for r in results if r.passed])
        avg_score = sum(r.score for r in results) / total if total else 0.0

        return EvalReport(
            suite=suite,
            total=total,
            passed=passed_count,
            avg_score=round(avg_score, 3),
            cases=results,
        )
