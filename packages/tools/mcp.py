from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


@dataclass
class MCPServer:
    server_id: str
    name: str
    endpoint: str
    auth_type: str = "none"
    enabled: bool = True


class MCPRegistry:
    def __init__(self, registry_path: Path) -> None:
        self._registry_path = registry_path
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._registry_path.exists():
            self._registry_path.write_text("[]\n", encoding="utf-8")

    def list_servers(self) -> list[MCPServer]:
        raw = json.loads(self._registry_path.read_text(encoding="utf-8"))
        return [MCPServer(**item) for item in raw]

    def register(self, server: MCPServer) -> MCPServer:
        servers = self.list_servers()
        for existing in servers:
            if existing.server_id == server.server_id:
                raise ValueError(f"server id already exists: {server.server_id}")
        servers.append(server)
        self._persist(servers)
        return server

    def set_enabled(self, server_id: str, enabled: bool) -> MCPServer:
        servers = self.list_servers()
        target: MCPServer | None = None
        for server in servers:
            if server.server_id == server_id:
                server.enabled = enabled
                target = server
                break
        if target is None:
            raise KeyError(server_id)
        self._persist(servers)
        return target

    def _persist(self, servers: list[MCPServer]) -> None:
        self._registry_path.write_text(
            json.dumps([asdict(server) for server in servers], indent=2) + "\n",
            encoding="utf-8",
        )


class MCPClient:
    def call_tool(self, server: MCPServer, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        if not server.enabled:
            raise RuntimeError(f"MCP server disabled: {server.server_id}")

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": args},
        }
        request = Request(
            server.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=10) as response:  # nosec B310
            body = json.loads(response.read().decode("utf-8"))

        if "error" in body:
            raise RuntimeError(str(body["error"]))
        return body.get("result") or {}
