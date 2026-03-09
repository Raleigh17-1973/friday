from __future__ import annotations

from business_ai.core.interfaces import Agent
from business_ai.core.models import AgentResult, TaskRequest
from business_ai.core.router import route_domain
from business_ai.memory.store import InMemoryContextStore


class Orchestrator:
    def __init__(self, agents: dict[str, Agent], memory: InMemoryContextStore) -> None:
        self._agents = agents
        self._memory = memory
        self._state: dict[str, dict[str, str]] = {}

    def run(self, task: TaskRequest) -> AgentResult:
        context = self._memory.load(task.project_id, task.conversation_id)
        prior_domain = self._state.get(task.conversation_id, {}).get("active_domain")

        domain, confidence = route_domain(task, conversation_domain=prior_domain)
        agent = self._agents.get(domain) or self._agents["communications"]
        result = agent.handle(task, context)

        self._state[task.conversation_id] = {"active_domain": result.domain}
        self._memory.append_event(
            project_id=task.project_id,
            conversation_id=task.conversation_id,
            event={
                "user_text": task.text,
                "domain": result.domain,
                "response": result.response,
                "confidence": confidence,
            },
        )
        return result
