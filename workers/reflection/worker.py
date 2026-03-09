from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
from uuid import uuid4

from packages.common.models import MemoryCandidate, RiskLevel


@dataclass
class ReflectionReport:
    run_id: str
    score: float
    heuristics: dict[str, bool]
    candidate_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ReflectionWorker:
    def reflect(self, run_trace, memory_service) -> ReflectionReport:
        final = run_trace.final_answer
        heuristics = {
            "has_next_steps": bool(final.recommended_next_steps),
            "has_risks": bool(final.major_risks),
            "has_assumptions": bool(final.key_assumptions),
            "has_critic": "critic_red_team" in run_trace.selected_agents,
        }

        score = sum(1.0 for ok in heuristics.values() if ok) / len(heuristics)

        candidates: list[MemoryCandidate] = []
        candidates.append(
            MemoryCandidate(
                candidate_id=f"mem_{uuid4().hex[:10]}",
                run_id=run_trace.run_id,
                candidate_type="reusable_lesson",
                content={
                    "lesson": "Include assumptions, risks, and next steps in every final package.",
                    "score": score,
                },
                risk_level=RiskLevel.MEDIUM,
                auto_accepted=False,
            )
        )

        candidate_ids: list[str] = []
        for candidate in candidates:
            payload = asdict(candidate)
            memory_service.add_candidate(payload, run_trace.org_id)
            candidate_ids.append(candidate.candidate_id)
            if candidate.auto_accepted:
                memory_service.promote_candidate(candidate.candidate_id, approved=True)

        return ReflectionReport(
            run_id=run_trace.run_id,
            score=round(score, 3),
            heuristics=heuristics,
            candidate_ids=candidate_ids,
        )
