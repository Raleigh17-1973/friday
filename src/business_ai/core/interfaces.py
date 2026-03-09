from __future__ import annotations

from abc import ABC, abstractmethod

from business_ai.core.models import AgentResult, TaskRequest


class Agent(ABC):
    domain: str

    @abstractmethod
    def can_handle(self, task: TaskRequest) -> bool:
        raise NotImplementedError

    @abstractmethod
    def handle(self, task: TaskRequest, context: dict) -> AgentResult:
        raise NotImplementedError
