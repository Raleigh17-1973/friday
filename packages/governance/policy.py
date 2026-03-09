from __future__ import annotations

from dataclasses import dataclass

from packages.common.models import ActionMode, RiskLevel


@dataclass
class PolicyDecision:
    allowed: bool
    requires_approval: bool
    reason: str


@dataclass
class ToolPolicyDecision:
    allowed: bool
    requires_approval: bool
    reason: str


class PolicyEngine:
    def evaluate(self, *, action_mode: ActionMode, requested_scopes: list[str], risk_level: RiskLevel) -> PolicyDecision:
        if action_mode == ActionMode.READ_ONLY:
            return PolicyDecision(allowed=True, requires_approval=False, reason="read-only")

        if action_mode == ActionMode.WRITE:
            if not requested_scopes:
                return PolicyDecision(allowed=False, requires_approval=False, reason="write scope missing")
            if risk_level in {RiskLevel.MEDIUM, RiskLevel.HIGH}:
                return PolicyDecision(
                    allowed=True,
                    requires_approval=True,
                    reason="write action with medium/high risk",
                )
            return PolicyDecision(allowed=True, requires_approval=True, reason="write action requires approval by default")

        return PolicyDecision(allowed=False, requires_approval=False, reason="unsupported action mode")

    def evaluate_tool_access(
        self,
        *,
        agent_id: str,
        tool_name: str,
        mode: ActionMode,
        allowed_tools: list[str],
        risk_level: RiskLevel,
    ) -> ToolPolicyDecision:
        if tool_name not in allowed_tools:
            return ToolPolicyDecision(
                allowed=False,
                requires_approval=False,
                reason=f"{agent_id} is not allowed to use {tool_name}",
            )

        if mode == ActionMode.READ_ONLY:
            return ToolPolicyDecision(allowed=True, requires_approval=False, reason="read-only tool call allowed")

        if mode == ActionMode.WRITE:
            if risk_level in {RiskLevel.MEDIUM, RiskLevel.HIGH}:
                return ToolPolicyDecision(allowed=True, requires_approval=True, reason="write tool call needs approval")
            return ToolPolicyDecision(
                allowed=True,
                requires_approval=True,
                reason="write tool call requires approval by default",
            )

        return ToolPolicyDecision(allowed=False, requires_approval=False, reason="unsupported tool mode")
