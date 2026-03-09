from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TaskRequest:
    text: str
    project_id: str
    conversation_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    domain: str
    response: str
    data: dict[str, Any] = field(default_factory=dict)
