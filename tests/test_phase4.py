import json
from pathlib import Path

import pytest

from apps.api.security import AdminAuth, HTTPException, RateLimiter
from packages.agents.registry import AgentRegistry
from packages.tools.mcp import MCPRegistry, MCPServer
from packages.tools.registry import ToolRegistry


class _FakeRequest:
    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = headers


def test_mcp_registry_register_and_toggle(tmp_path: Path) -> None:
    reg = MCPRegistry(tmp_path / "mcp_servers.json")
    server = reg.register(MCPServer(server_id="crm", name="CRM", endpoint="http://localhost:8123"))
    assert server.server_id == "crm"

    listed = reg.list_servers()
    assert len(listed) == 1
    assert listed[0].enabled

    updated = reg.set_enabled("crm", False)
    assert updated.enabled is False


def test_tool_registry_lists_function_and_mcp_tools(tmp_path: Path) -> None:
    mcp = MCPRegistry(tmp_path / "mcp_servers.json")
    mcp.register(MCPServer(server_id="erp", name="ERP", endpoint="http://localhost:8124"))
    tools = ToolRegistry(mcp).list_tools()
    ids = [tool["tool_id"] for tool in tools]
    assert "web.research" in ids
    assert "docs.retrieve" in ids
    assert "mcp::erp" in ids


def test_agent_registry_update_status_in_temp_dir(tmp_path: Path) -> None:
    manifests_src = Path(__file__).resolve().parents[1] / "packages" / "agents" / "manifests"
    manifests_dst = tmp_path / "manifests"
    manifests_dst.mkdir(parents=True, exist_ok=True)

    src_file = manifests_src / "finance.json"
    dst_file = manifests_dst / "finance.json"
    dst_file.write_text(src_file.read_text(encoding="utf-8"), encoding="utf-8")

    registry = AgentRegistry(manifests_dst)
    updated = registry.update_status("finance", "deprecated")
    assert updated.status == "deprecated"

    loaded = json.loads(dst_file.read_text(encoding="utf-8"))
    assert loaded["status"] == "deprecated"


def test_admin_auth_and_rate_limiter(monkeypatch) -> None:
    monkeypatch.setenv("FRIDAY_ADMIN_API_KEY", "secret")
    auth = AdminAuth()
    auth.require(_FakeRequest({"x-admin-api-key": "secret"}))

    limiter = RateLimiter(requests_per_minute=2)
    limiter.check("k1")
    limiter.check("k1")
    with pytest.raises(HTTPException):
        limiter.check("k1")
