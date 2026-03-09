from __future__ import annotations

from collections import defaultdict
from typing import Any


class InMemoryContextStore:
    def __init__(self) -> None:
        self._project_history: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._conversation_history: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def load(self, project_id: str, conversation_id: str) -> dict[str, list[dict[str, Any]]]:
        return {
            "project_history": list(self._project_history[project_id][-25:]),
            "conversation_history": list(self._conversation_history[conversation_id][-25:]),
        }

    def append_event(self, project_id: str, conversation_id: str, event: dict[str, Any]) -> None:
        self._project_history[project_id].append(event)
        self._conversation_history[conversation_id].append(event)
