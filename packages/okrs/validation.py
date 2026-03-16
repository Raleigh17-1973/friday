from __future__ import annotations

"""OKR validation engine — enforces writing quality and structural rules."""

import re
from dataclasses import dataclass, field

from packages.okrs.models import Objective, KeyResult, ValidationIssue

# ─── Vocabulary sets ──────────────────────────────────────────────────────────

ACTIVITY_VERBS: set[str] = {
    "analyze", "analyse", "help", "participate", "consult", "support",
    "assist", "facilitate", "review", "attend", "coordinate", "organize",
    "organise", "track", "monitor", "maintain", "manage", "oversee",
    "conduct", "ensure", "continue", "establish", "implement",
}

PERF_LANGUAGE: set[str] = {
    "rated", "evaluated", "performance score", "performance review",
    "bonus", "compensation", "salary", "raise", "promotion",
    "performance rating", "performance evaluation", "merit",
}

OUTCOME_VERBS: set[str] = {
    "achieve", "grow", "increase", "decrease", "reduce", "improve",
    "deliver", "launch", "reach", "attain", "generate", "expand",
    "retain", "acquire", "build", "create", "transform", "double",
    "triple", "eliminate", "accelerate", "maximize", "minimize",
}


def _first_word(text: str) -> str:
    """Return the first word of text, lowercased."""
    words = text.strip().split()
    return words[0].lower() if words else ""


def _contains_any(text: str, phrases: set[str]) -> str | None:
    """Return the first matching phrase found in text (case-insensitive), or None."""
    lowered = text.lower()
    for phrase in phrases:
        if phrase in lowered:
            return phrase
    return None


class OKRValidator:
    """Validates Objective and KeyResult objects against OKR writing rules."""

    # ── Objective validation ──────────────────────────────────────────────────

    def validate_objective(
        self,
        obj: Objective,
        existing_for_period: list[Objective],
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        # Rule OBJ-01: max 5 objectives per org_node per period
        peer_count = sum(
            1
            for o in existing_for_period
            if o.org_node_id == obj.org_node_id
            and o.objective_id != obj.objective_id
            and o.status not in ("archived", "graded")
        )
        if peer_count >= 5:
            issues.append(ValidationIssue(
                rule_id="OBJ-01",
                severity="error",
                message=(
                    f"This org node already has {peer_count} active objectives for this period. "
                    "OKR methodology recommends no more than 5 objectives per team per cycle."
                ),
                field="org_node_id",
                suggestion="Archive or merge lower-priority objectives before adding a new one.",
            ))

        # Rule OBJ-02: title must contain an outcome-oriented verb
        title_lower = obj.title.lower()
        has_outcome = any(v in title_lower for v in OUTCOME_VERBS)
        if not has_outcome:
            issues.append(ValidationIssue(
                rule_id="OBJ-02",
                severity="warning",
                message=(
                    "Objective title does not appear to contain an outcome-oriented verb "
                    "(e.g., 'Grow', 'Achieve', 'Reduce', 'Launch')."
                ),
                field="title",
                suggestion=(
                    "Rewrite as: '[Outcome verb] + [measurable result] + [impact]'. "
                    "Example: 'Grow enterprise NPS from 42 to 65 to become a category leader.'"
                ),
            ))

        # Rule OBJ-03: committed objective must have a sponsor
        if obj.objective_type == "committed" and not obj.sponsor_user_id:
            issues.append(ValidationIssue(
                rule_id="OBJ-03",
                severity="error",
                message="Committed objectives require a sponsor_user_id to ensure executive accountability.",
                field="sponsor_user_id",
                suggestion="Assign a senior sponsor who will remove blockers and escalate misses.",
            ))

        # Rule OBJ-04: compensation / performance language
        match = _contains_any(obj.title + " " + obj.description + " " + obj.rationale, PERF_LANGUAGE)
        if match:
            issues.append(ValidationIssue(
                rule_id="OBJ-04",
                severity="error",
                message=(
                    f"Objective contains performance-review language ('{match}'). "
                    "OKRs must never be linked to compensation or performance ratings."
                ),
                field="title",
                suggestion=(
                    "Remove all references to bonuses, ratings, or compensation. "
                    "OKRs are a goal-setting tool, not a performance-management tool."
                ),
            ))

        # Rule OBJ-05: alignment warning — no parent and mode is inherited
        if obj.alignment_mode == "inherited" and not obj.parent_objective_id:
            issues.append(ValidationIssue(
                rule_id="OBJ-05",
                severity="warning",
                message=(
                    "Objective has alignment_mode='inherited' but no parent_objective_id. "
                    "Without a parent link, cascade alignment cannot be verified."
                ),
                field="parent_objective_id",
                suggestion=(
                    "Link to a parent company or business-unit objective, or change "
                    "alignment_mode to 'contributed' or 'shared'."
                ),
            ))

        return issues

    # ── Key result validation ─────────────────────────────────────────────────

    def validate_key_result(
        self,
        kr: KeyResult,
        objective: Objective,
        existing_krs_for_objective: list[KeyResult] | None = None,
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        existing = existing_krs_for_objective or []

        # Rule KR-01: max 5 KRs per objective
        peer_count = sum(
            1
            for k in existing
            if k.kr_id != kr.kr_id and k.status != "archived"
        )
        if peer_count >= 5:
            issues.append(ValidationIssue(
                rule_id="KR-01",
                severity="error",
                message=(
                    f"This objective already has {peer_count} active key results. "
                    "OKR methodology recommends no more than 5 KRs per objective."
                ),
                field="objective_id",
                suggestion="Consolidate or remove lower-value key results before adding another.",
            ))

        # Rule KR-02: owner required
        if not kr.owner_user_id or kr.owner_user_id == "":
            issues.append(ValidationIssue(
                rule_id="KR-02",
                severity="error",
                message="Every key result must have a named owner.",
                field="owner_user_id",
                suggestion="Assign the person accountable for tracking and updating this metric.",
            ))

        # Rule KR-03: metric KR must have baseline and target
        if kr.kr_type == "metric":
            if kr.baseline_value is None:
                issues.append(ValidationIssue(
                    rule_id="KR-03a",
                    severity="error",
                    message="Metric key results require a baseline_value so progress can be measured.",
                    field="baseline_value",
                    suggestion=(
                        "State where you are today. If unknown, run a measurement sprint first "
                        "and add the KR once you have a baseline."
                    ),
                ))
            if kr.target_value is None:
                issues.append(ValidationIssue(
                    rule_id="KR-03b",
                    severity="error",
                    message="Metric key results require a target_value to define success.",
                    field="target_value",
                    suggestion="Define the specific number that constitutes achieving this result.",
                ))

        # Rule KR-04: binary KR must have acceptance criteria in description
        if kr.kr_type == "binary":
            description = (kr.description or "").strip()
            if len(description) < 20:
                issues.append(ValidationIssue(
                    rule_id="KR-04",
                    severity="error",
                    message=(
                        "Binary key results require clear acceptance criteria in the description "
                        "so there is no ambiguity about what 'done' means."
                    ),
                    field="description",
                    suggestion=(
                        "Write at least 1–2 sentences describing the conditions that must be "
                        "true for this KR to be marked complete."
                    ),
                ))

        # Rule KR-05: activity-based title (starts with activity verb)
        first = _first_word(kr.title)
        if first in ACTIVITY_VERBS:
            issues.append(ValidationIssue(
                rule_id="KR-05",
                severity="error",
                message=(
                    f"Key result title starts with an activity verb ('{first}'). "
                    "KRs must describe measurable outcomes, not activities or tasks."
                ),
                field="title",
                suggestion=(
                    f"Convert from activity to outcome. Instead of '{kr.title}', "
                    "write what measurable change that activity produces. "
                    "Example: 'Analyze churn' → 'Reduce monthly churn rate from 4.2% to 2.5%'."
                ),
            ))

        # Rule KR-06: quarterly period requires weekly check-ins
        # (caller should pass period data; we use a simple frequency check)
        if kr.checkin_frequency not in ("weekly", "biweekly", "monthly"):
            issues.append(ValidationIssue(
                rule_id="KR-06",
                severity="warning",
                message=f"Unrecognised check-in frequency '{kr.checkin_frequency}'.",
                field="checkin_frequency",
                suggestion="Use 'weekly', 'biweekly', or 'monthly'.",
            ))

        # Rule KR-07: committed KR should have a due_date
        if objective.objective_type == "committed" and not kr.due_date:
            issues.append(ValidationIssue(
                rule_id="KR-07",
                severity="warning",
                message="Committed key results should have an explicit due_date.",
                field="due_date",
                suggestion=(
                    "Set a due date that aligns with or precedes the parent period end date."
                ),
            ))

        # Rule KR-08: manual data source without source reference
        if kr.data_source_type == "manual" and not kr.source_reference:
            issues.append(ValidationIssue(
                rule_id="KR-08",
                severity="warning",
                message="Manual-tracked metric has no source_reference.",
                field="source_reference",
                suggestion=(
                    "Document where this data comes from (e.g., 'Salesforce Opportunity report', "
                    "'Weekly ops meeting notes') so the metric can be audited."
                ),
            ))

        # Rule KR-09: compensation / performance language
        match = _contains_any(kr.title + " " + (kr.description or ""), PERF_LANGUAGE)
        if match:
            issues.append(ValidationIssue(
                rule_id="KR-09",
                severity="error",
                message=(
                    f"Key result contains performance-review language ('{match}'). "
                    "OKRs must never be linked to compensation or ratings."
                ),
                field="title",
                suggestion="Remove all references to compensation, bonuses, or performance scores.",
            ))

        return issues

    # ── Convenience method: validate objective + all its KRs ─────────────────

    def validate_objective_with_krs(
        self,
        obj: Objective,
        existing_for_period: list[Objective],
        krs: list[KeyResult],
    ) -> dict[str, list[ValidationIssue]]:
        result: dict[str, list[ValidationIssue]] = {
            "objective": self.validate_objective(obj, existing_for_period),
            "key_results": {},
        }
        for kr in krs:
            result["key_results"][kr.kr_id] = self.validate_key_result(
                kr, obj, [k for k in krs if k.kr_id != kr.kr_id]
            )
        return result
