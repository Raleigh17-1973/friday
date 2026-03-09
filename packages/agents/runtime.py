from __future__ import annotations

from dataclasses import dataclass, field

from packages.common.models import PlannerOutput, SpecialistMemo


@dataclass
class Specialist:
    specialist_id: str
    purpose: str
    shared_rules: list[str] = field(default_factory=list)

    def run(self, plan: PlannerOutput, user_message: str) -> SpecialistMemo:
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
            "Escalation note: Escalate when unknowns are material, evidence is contradictory, or risk is medium/high.",
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
