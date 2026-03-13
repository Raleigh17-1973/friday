from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packages.agents.runtime import Specialist

SHARED_SPECIALIST_RULES: tuple[str, ...] = (
    "All specialists return structured memos, not raw chat.",
    "All specialists distinguish facts, assumptions, and unknowns.",
    "All specialists are read-only unless explicitly upgraded.",
    "All specialists include confidence and escalation notes.",
    "All specialists can be overruled only by Friday's synthesis step, not by silence.",
)


@dataclass
class AgentManifest:
    id: str
    name: str
    purpose: str
    trigger_conditions: list[str]
    anti_trigger_conditions: list[str]
    tools_allowed: list[str]
    risk_level: str
    system_prompt_path: str
    input_schema: str
    output_schema: str
    eval_dataset_id: str
    owner: str
    status: str


class AgentRegistry:
    def __init__(self, manifests_dir: Path) -> None:
        self._manifests_dir = manifests_dir
        self._manifests: dict[str, AgentManifest] = {}
        self._load()

    def _load(self) -> None:
        self._manifests = {}
        for path in sorted(self._manifests_dir.glob("*.json")):
            data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            manifest = AgentManifest(**data)
            self._manifests[manifest.id] = manifest

    def list_active(self) -> list[AgentManifest]:
        return [manifest for manifest in self._manifests.values() if manifest.status == "active"]

    def get(self, agent_id: str) -> AgentManifest | None:
        return self._manifests.get(agent_id)

    def build_specialist(self, agent_id: str) -> Specialist:
        manifest = self._manifests.get(agent_id)
        if manifest is None:
            raise KeyError(f"Unknown agent: {agent_id}")

        # Load the rich .md system prompt.
        # manifests_dir = packages/agents/manifests → .parent.parent.parent = project root
        system_prompt = ""
        if manifest.system_prompt_path:
            project_root = self._manifests_dir.parent.parent.parent
            prompt_path = project_root / manifest.system_prompt_path
            if prompt_path.exists():
                system_prompt = prompt_path.read_text(encoding="utf-8").strip()

        return Specialist(
            specialist_id=manifest.id,
            purpose=manifest.purpose,
            shared_rules=list(SHARED_SPECIALIST_RULES),
            system_prompt=system_prompt,
        )

    def allowed_tools_for(self, agent_id: str) -> list[str]:
        manifest = self._manifests.get(agent_id)
        if manifest is None:
            return []
        return list(manifest.tools_allowed)

    def update_status(self, agent_id: str, status: str) -> AgentManifest:
        manifest = self._manifests.get(agent_id)
        if manifest is None:
            raise KeyError(agent_id)
        if status not in {"draft", "active", "deprecated"}:
            raise ValueError("status must be one of: draft, active, deprecated")

        path = self._manifests_dir / f"{agent_id}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["status"] = status
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        self._load()
        return self._manifests[agent_id]
