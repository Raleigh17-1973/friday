from __future__ import annotations

from packages.common.models import CriticReport, SpecialistMemo


def run_critic(memos: list[SpecialistMemo]) -> CriticReport:
    assumptions = [assumption for memo in memos for assumption in memo.assumptions]
    risks = [risk for memo in memos for risk in memo.risks]

    return CriticReport(
        blind_spots=[
            "Potential resource constraints may be underestimated.",
            "Dependencies across teams may be missing explicit ownership.",
        ],
        challenged_assumptions=assumptions[:3],
        alternative_path="Run a 2-week pilot with explicit success gates before full rollout.",
        residual_risks=risks[:4],
    )
