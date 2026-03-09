from __future__ import annotations

from business_ai.core.interfaces import Agent
from business_ai.core.models import AgentResult, TaskRequest


class CommunicationsAgent(Agent):
    domain = "communications"

    def can_handle(self, task: TaskRequest) -> bool:
        return True

    def handle(self, task: TaskRequest, context: dict) -> AgentResult:
        text = task.text.strip()
        lowered = text.lower()
        if "status email" in lowered or "status update" in lowered:
            response = (
                "Use this project status email structure:\n"
                "1. Overall status (Green/Yellow/Red) and why\n"
                "2. What changed since last update\n"
                "3. Top risks/blockers with owners\n"
                "4. Decisions needed and by when\n"
                "5. Next 7-day plan"
            )
        else:
            response = (
                "Communications guidance:\n"
                "Start with audience, objective, and action requested.\n"
                "Then draft the message in plain language with one clear call to action.\n"
                f"Request summary: {text}"
            )
        return AgentResult(domain=self.domain, response=response, data={"mode": "comms"})
