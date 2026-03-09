from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from packages.tools.mcp import MCPRegistry


@dataclass
class ToolDefinition:
    tool_id: str
    source: str
    mode: str
    scopes: list[str]
    enabled: bool
    meta: dict[str, Any]


class ToolRegistry:
    def __init__(self, mcp_registry: MCPRegistry) -> None:
        self._mcp_registry = mcp_registry
        self._function_tools: dict[str, ToolDefinition] = {
            "web.research": ToolDefinition(
                tool_id="web.research",
                source="function",
                mode="read_only",
                scopes=["research.read"],
                enabled=True,
                meta={"description": "Web research retrieval"},
            ),
            "docs.retrieve": ToolDefinition(
                tool_id="docs.retrieve",
                source="function",
                mode="read_only",
                scopes=["docs.read"],
                enabled=True,
                meta={"description": "Repository document retrieval"},
            ),
        }

    def list_tools(self) -> list[dict[str, Any]]:
        tools = [asdict(tool) for tool in self._function_tools.values()]
        for server in self._mcp_registry.list_servers():
            tools.append(
                {
                    "tool_id": f"mcp::{server.server_id}",
                    "source": "mcp",
                    "mode": "read_only",
                    "scopes": ["mcp.call"],
                    "enabled": server.enabled,
                    "meta": {
                        "server_id": server.server_id,
                        "name": server.name,
                        "endpoint": server.endpoint,
                    },
                }
            )
        return tools
