from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from packages.common.models import PlannerOutput, SpecialistMemo

if TYPE_CHECKING:
    from packages.llm.base import LLMProvider

# Fallback system prompt used when no .md prompt file is loaded
_SPECIALIST_SYSTEM_FALLBACK = """\
You are Friday's {purpose} specialist.
Your job is to analyze business problems and produce a structured expert memo.

Rules:
{rules}
"""

# Tree-of-thought contract — replaces _OUTPUT_CONTRACT when risk_level is HIGH
_OUTPUT_CONTRACT_TOT = """
---
## Response Format (HIGH RISK — Tree-of-Thought Mode)

This request is classified HIGH RISK. You must reason through three distinct scenarios before committing to a recommendation. This reduces overconfidence and surfaces the full decision space.

Respond ONLY with valid JSON (no markdown fences):
{
  "analysis": "<overall analysis — the core issue and what drives the outcome difference across scenarios>",
  "scenarios": {
    "optimistic": {
      "description": "<what must be true for the best case>",
      "outcome": "<specific, quantified outcome if possible>",
      "probability": <0.0-1.0>,
      "key_driver": "<the single variable that makes this scenario possible>"
    },
    "base": {
      "description": "<most likely outcome given current evidence>",
      "outcome": "<specific, quantified outcome if possible>",
      "probability": <0.0-1.0>,
      "key_driver": "<the primary uncertainty driving this outcome>"
    },
    "pessimistic": {
      "description": "<realistic downside — not catastrophizing>",
      "outcome": "<specific, quantified outcome if possible>",
      "probability": <0.0-1.0>,
      "key_driver": "<what makes the downside likely>"
    }
  },
  "recommendation": "<which scenario should be planned for, and why — must be GO / NO-GO / CONDITIONAL>",
  "assumptions": ["<each assumption that determines which scenario materializes>"],
  "risks": ["<risks that could push outcome toward pessimistic>"],
  "evidence": ["<data from the problem statement used in your analysis>"],
  "confidence": <0.0-1.0 float>,
  "questions": ["<only if a specific unknown would materially shift your scenario probabilities>"]
}

CRITICAL:
1. Scenario probabilities must sum to 1.0
2. Base case probability must be highest (this is the most likely outcome)
3. Each scenario must have a distinct, specific key driver — not generic labels
4. Anti-sycophancy: the optimistic scenario is not the plan — it is an upper bound
"""

# Appended to every specialist prompt (loaded or fallback) to enforce output format + quality
_OUTPUT_CONTRACT = """
---
## Response Format

You are operating as an internal specialist agent. The synthesizer will combine your memo with other specialists into a final deliverable. Do your analysis rigorously.

Respond ONLY with valid JSON (no markdown fences):
{
  "analysis": "<detailed analysis — if numbers are provided, USE them; show calculations, not just conclusions>",
  "recommendation": "<ONE clear recommendation — GO / NO-GO / CONDITIONAL with your reasoning; never say 'it depends' without specifying what>",
  "assumptions": ["<state every assumption explicitly, especially ones that would change your recommendation if wrong>"],
  "risks": ["<specific risk with likelihood and impact where possible>"],
  "evidence": ["<data point or calculation from the problem statement>"],
  "confidence": <0.0-1.0 float>,
  "questions": ["<only list if critical data is genuinely absent and your recommendation depends on it>"],
  "tool_requests": []
}

The `tool_requests` field is OPTIONAL. Only populate it if you have been explicitly instructed to create or update a business object (OKR, process, task, decision) AND your system prompt confirms you have write access. When empty, omit or leave as []. When populated, each entry must be: {"tool": "<tool_id>", "args": {<tool-specific fields>}}.

CRITICAL QUALITY RULES:
1. If the problem includes numbers (costs, hours, %, headcount), compute with them — do not say "you would need to calculate"
2. Your recommendation must be a clear directive — not "consider", "explore", or "it depends"
3. Anti-sycophancy: your job is to find the real risks and gaps, not to validate what sounds good
4. If the answer is obvious, say so clearly and give your confidence level
5. Confidence 0.9+ = high certainty; 0.7-0.9 = solid reasoning, minor gaps; below 0.7 = flag what you need
"""


@dataclass
class Specialist:
    specialist_id: str
    purpose: str
    shared_rules: list[str] = field(default_factory=list)
    system_prompt: str = field(default="")
    llm: "LLMProvider | None" = field(default=None, repr=False)

    def run(self, plan: PlannerOutput, user_message: str, tot_mode: bool = False) -> SpecialistMemo:
        """Run the specialist, optionally in tree-of-thought (3-scenario) mode.

        ``tot_mode`` is automatically set to True when ``plan.risk_level`` is HIGH
        by the orchestrator.  The specialist generates optimistic / base / pessimistic
        scenarios and the synthesizer picks the best-supported path.
        """
        if self.llm is not None:
            try:
                return self._run_with_llm(plan, user_message, tot_mode=tot_mode)
            except Exception:
                pass
        return self._run_stub(plan, user_message)

    def _build_system_prompt(self, tot_mode: bool = False) -> str:
        contract = _OUTPUT_CONTRACT_TOT if tot_mode else _OUTPUT_CONTRACT
        if self.system_prompt:
            return self.system_prompt + "\n" + contract
        else:
            rules_text = "\n".join(f"- {r}" for r in self.shared_rules) if self.shared_rules else "- Be precise and evidence-based."
            base = _SPECIALIST_SYSTEM_FALLBACK.format(purpose=self.purpose, rules=rules_text)
            return base + contract

    def _run_with_llm(self, plan: PlannerOutput, user_message: str, tot_mode: bool = False) -> SpecialistMemo:
        assert self.llm is not None
        system = self._build_system_prompt(tot_mode=tot_mode)
        prompt = (
            f"Problem: {user_message}\n\n"
            f"Planner context:\n"
            f"- Domains involved: {', '.join(plan.domains_involved) or 'general'}\n"
            f"- Risk level: {plan.risk_level.value}\n"
            f"- Output format requested: {plan.output_format}\n"
            f"- Missing information (if any): {', '.join(plan.missing_information) or 'none identified'}"
        )
        max_tokens = 2000 if tot_mode else 1500
        parsed = self.llm.complete_json(system, prompt, max_tokens=max_tokens)
        if parsed and "analysis" in parsed and "recommendation" in parsed:
            raw_requests = parsed.get("tool_requests", [])
            tool_requests = [r for r in raw_requests if isinstance(r, dict) and "tool" in r and "args" in r]
            return SpecialistMemo(
                specialist_id=self.specialist_id,
                analysis=str(parsed.get("analysis", "")),
                recommendation=str(parsed.get("recommendation", "")),
                assumptions=list(parsed.get("assumptions", [])),
                risks=list(parsed.get("risks", [])),
                evidence=list(parsed.get("evidence", [])),
                confidence=float(parsed.get("confidence", 0.75)),
                questions=list(parsed.get("questions", [])),
                scenarios=parsed.get("scenarios") if tot_mode else None,
                tool_requests=tool_requests,
            )
        raise ValueError("LLM returned unparseable specialist memo")

    def _run_stub(self, plan: PlannerOutput, user_message: str) -> SpecialistMemo:
        text = user_message.lower()
        facts = [
            f"Planner domains: {', '.join(plan.domains_involved) or 'none'}",
            f"Planner risk level: {plan.risk_level.value}",
            f"Requested output format: {plan.output_format}",
        ]
        assumptions = [
            "Constraints are accurate as provided.",
            "No hidden compliance blockers exist unless flagged.",
            "Read-only advisory mode applies unless Friday explicitly upgrades permissions.",
        ]
        unknowns = plan.missing_information or ["No explicit unknowns were provided by the planner."]
        risks = [
            "Execution risk if ownership is unclear.",
            "Decision quality drops if missing information is ignored.",
            f"Escalation note: connect an LLM provider for real {self.specialist_id} analysis.",
        ]
        evidence = [*facts, *[f"Registry rule: {rule}" for rule in self.shared_rules]]
        analysis = "\n".join(
            [
                "Structured memo:",
                "Facts:",
                *[f"- {item}" for item in facts],
                "Assumptions:",
                *[f"- {item}" for item in assumptions],
                "Unknowns:",
                *[f"- {item}" for item in unknowns],
            ]
        )
        return SpecialistMemo(
            specialist_id=self.specialist_id,
            analysis=f"{self.purpose} analysis for: {user_message}\n\n{analysis}",
            recommendation=self._recommendation_for(text, plan.output_format),
            assumptions=assumptions,
            risks=risks,
            evidence=evidence,
            confidence=0.68,
            questions=unknowns,
        )

    def _recommendation_for(self, text: str, output_format: str) -> str:
        if output_format == "business_case_draft":
            if self.specialist_id == "finance":
                return (
                    "Build the financial model with baseline conversion, win rate, cycle time, and average deal size; "
                    "then calculate expected uplift, implementation cost, and payback period."
                )
            if self.specialist_id == "sales_revenue":
                return (
                    "Scope 1-2 sales workflow use cases (e.g., lead qualification, call prep, follow-up drafting) "
                    "and define adoption targets per role."
                )
            if self.specialist_id == "operations":
                return (
                    "Define pilot process changes, instrumentation, and owner-level accountability so outcomes are measurable."
                )
            if self.specialist_id == "writer_scribe":
                return (
                    "Package the recommendation into an executive-ready business case with assumptions, tradeoffs, and decisions."
                )
        if self.specialist_id == "project_manager":
            return (
                "Build a PMBOK-aligned project package: charter, scope boundaries, stakeholder ownership, "
                "milestone schedule, RAID controls, and governance cadence."
            )
        if "template" in text and self.specialist_id == "writer_scribe":
            return "Provide a fill-in template with sections, formulas, and required decision fields."
        return f"Apply a {self.specialist_id} lens with explicit owners, timeline, and metrics."
