from __future__ import annotations

import json
from typing import TYPE_CHECKING

from packages.common.models import CriticReport, SpecialistMemo

if TYPE_CHECKING:
    from packages.llm.base import LLMProvider

_CRITIC_SYSTEM = """\
You are Friday's critic agent. Your job is adversarial review — find what the specialists missed.

Given a set of specialist memos, identify:
- Blind spots and unstated risks
- Assumptions that deserve challenge
- A stronger or more conservative alternative approach
- Residual risks that remain even if recommendations are followed

Respond ONLY with valid JSON (no markdown fences):
{
  "blind_spots": ["<risk or gap not addressed by specialists>"],
  "challenged_assumptions": ["<assumption that may not hold>"],
  "alternative_path": "<one-sentence description of a more conservative or different approach>",
  "residual_risks": ["<risk that remains even after following recommendations>"]
}"""


def run_critic(memos: list[SpecialistMemo], llm: "LLMProvider | None" = None) -> CriticReport:
    assumptions = [assumption for memo in memos for assumption in memo.assumptions]
    risks = [risk for memo in memos for risk in memo.risks]

    if llm is not None and memos:
        try:
            memos_text = "\n\n".join(
                f"Specialist: {m.specialist_id}\nAnalysis: {m.analysis}\nRecommendation: {m.recommendation}\n"
                f"Assumptions: {json.dumps(m.assumptions)}\nRisks: {json.dumps(m.risks)}"
                for m in memos
            )
            parsed = llm.complete_json(_CRITIC_SYSTEM, f"Specialist memos to review:\n\n{memos_text}")
            if parsed and "blind_spots" in parsed:
                return CriticReport(
                    blind_spots=list(parsed.get("blind_spots", [])),
                    challenged_assumptions=list(parsed.get("challenged_assumptions", [])),
                    alternative_path=str(parsed.get("alternative_path", "")),
                    residual_risks=list(parsed.get("residual_risks", [])),
                )
        except Exception:
            pass

    return CriticReport(
        blind_spots=[
            "Potential resource constraints may be underestimated.",
            "Dependencies across teams may be missing explicit ownership.",
        ],
        challenged_assumptions=assumptions[:3],
        alternative_path="Run a 2-week pilot with explicit success gates before full rollout.",
        residual_risks=risks[:4],
    )
