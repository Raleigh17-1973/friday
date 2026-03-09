from __future__ import annotations

from business_ai.core.interfaces import Agent
from business_ai.core.models import AgentResult, TaskRequest


class GenericDomainAgent(Agent):
    def __init__(self, domain: str, specialty: str) -> None:
        self.domain = domain
        self._specialty = specialty

    def can_handle(self, task: TaskRequest) -> bool:
        return True

    def handle(self, task: TaskRequest, context: dict) -> AgentResult:
        prior_turns = len(context.get("conversation_history", []))
        response = (
            f"{self.domain.replace('_', ' ').title()} perspective:\n"
            f"I will handle this as a {self._specialty} problem.\n"
            "1. Clarify objective and success metric.\n"
            "2. Identify constraints, risks, and dependencies.\n"
            "3. Propose an executable plan with owner and timeline.\n"
            f"Your request: {task.text.strip()}"
        )
        return AgentResult(domain=self.domain, response=response, data={"prior_turns": prior_turns})
