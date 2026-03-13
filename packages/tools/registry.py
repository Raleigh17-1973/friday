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
                tool_id="web.research", source="function", mode="read_only",
                scopes=["research.read"], enabled=True,
                meta={"description": "Web research retrieval"},
            ),
            "docs.retrieve": ToolDefinition(
                tool_id="docs.retrieve", source="function", mode="read_only",
                scopes=["docs.read"], enabled=True,
                meta={"description": "Repository document retrieval"},
            ),
            # Phase 1: Document generation
            "docs.generate": ToolDefinition(
                tool_id="docs.generate", source="function", mode="write",
                scopes=["docs.write"], enabled=True,
                meta={"description": "Generate Word, PowerPoint, Excel, or PDF documents"},
            ),
            "templates.list": ToolDefinition(
                tool_id="templates.list", source="function", mode="read_only",
                scopes=["templates.read"], enabled=True,
                meta={"description": "List available document templates"},
            ),
            "templates.read": ToolDefinition(
                tool_id="templates.read", source="function", mode="read_only",
                scopes=["templates.read"], enabled=True,
                meta={"description": "Get template details"},
            ),
            # Phase 2: Google Workspace
            "google.docs.create": ToolDefinition(
                tool_id="google.docs.create", source="function", mode="write",
                scopes=["google.write"], enabled=True,
                meta={"description": "Create a Google Doc"},
            ),
            "google.slides.create": ToolDefinition(
                tool_id="google.slides.create", source="function", mode="write",
                scopes=["google.write"], enabled=True,
                meta={"description": "Create a Google Slides presentation"},
            ),
            "google.sheets.create": ToolDefinition(
                tool_id="google.sheets.create", source="function", mode="write",
                scopes=["google.write"], enabled=True,
                meta={"description": "Create a Google Sheets spreadsheet"},
            ),
            # Phase 3: Communication
            "email.draft": ToolDefinition(
                tool_id="email.draft", source="function", mode="write",
                scopes=["email.write"], enabled=True,
                meta={"description": "Create an email draft"},
            ),
            "email.send": ToolDefinition(
                tool_id="email.send", source="function", mode="write",
                scopes=["email.write"], enabled=True,
                meta={"description": "Send an email (requires approval)"},
            ),
            "email.read": ToolDefinition(
                tool_id="email.read", source="function", mode="read_only",
                scopes=["email.read"], enabled=True,
                meta={"description": "Read inbox messages"},
            ),
            "calendar.availability": ToolDefinition(
                tool_id="calendar.availability", source="function", mode="read_only",
                scopes=["calendar.read"], enabled=True,
                meta={"description": "Check calendar availability"},
            ),
            "calendar.create_event": ToolDefinition(
                tool_id="calendar.create_event", source="function", mode="write",
                scopes=["calendar.write"], enabled=True,
                meta={"description": "Create a calendar event"},
            ),
            "slack.post": ToolDefinition(
                tool_id="slack.post", source="function", mode="write",
                scopes=["slack.write"], enabled=True,
                meta={"description": "Post a Slack message"},
            ),
            "slack.read": ToolDefinition(
                tool_id="slack.read", source="function", mode="read_only",
                scopes=["slack.read"], enabled=True,
                meta={"description": "Read Slack channel messages"},
            ),
            # Phase 4: Analytics
            "analytics.chart": ToolDefinition(
                tool_id="analytics.chart", source="function", mode="write",
                scopes=["analytics.write"], enabled=True,
                meta={"description": "Generate a chart from data"},
            ),
            "analytics.kpi_status": ToolDefinition(
                tool_id="analytics.kpi_status", source="function", mode="read_only",
                scopes=["analytics.read"], enabled=True,
                meta={"description": "Get current KPI values and trends"},
            ),
            # Phase 5: Project management
            "jira.create_issue": ToolDefinition(
                tool_id="jira.create_issue", source="function", mode="write",
                scopes=["jira.write"], enabled=True,
                meta={"description": "Create a Jira issue"},
            ),
            "jira.search": ToolDefinition(
                tool_id="jira.search", source="function", mode="read_only",
                scopes=["jira.read"], enabled=True,
                meta={"description": "Search Jira issues (JQL)"},
            ),
            "okrs.status": ToolDefinition(
                tool_id="okrs.status", source="function", mode="read_only",
                scopes=["okrs.read"], enabled=True,
                meta={"description": "Get OKR status and progress"},
            ),
            # Phase 6: Knowledge
            "confluence.read": ToolDefinition(
                tool_id="confluence.read", source="function", mode="read_only",
                scopes=["confluence.read"], enabled=True,
                meta={"description": "Read Confluence pages"},
            ),
            "notion.read": ToolDefinition(
                tool_id="notion.read", source="function", mode="read_only",
                scopes=["notion.read"], enabled=True,
                meta={"description": "Read Notion pages"},
            ),
            "brand_assets.read": ToolDefinition(
                tool_id="brand_assets.read", source="function", mode="read_only",
                scopes=["brand.read"], enabled=True,
                meta={"description": "Read brand guidelines and assets"},
            ),
            "styleguide.read": ToolDefinition(
                tool_id="styleguide.read", source="function", mode="read_only",
                scopes=["brand.read"], enabled=True,
                meta={"description": "Read brand style guide"},
            ),
            # Phase 7: Finance & CRM
            "finance.create_invoice": ToolDefinition(
                tool_id="finance.create_invoice", source="function", mode="write",
                scopes=["finance.write"], enabled=True,
                meta={"description": "Generate an invoice"},
            ),
            "finance.budget_status": ToolDefinition(
                tool_id="finance.budget_status", source="function", mode="read_only",
                scopes=["finance.read"], enabled=True,
                meta={"description": "Check budget vs actuals"},
            ),
            "salesforce.get_pipeline": ToolDefinition(
                tool_id="salesforce.get_pipeline", source="function", mode="read_only",
                scopes=["crm.read"], enabled=True,
                meta={"description": "Get Salesforce sales pipeline"},
            ),
            "hubspot.get_deals": ToolDefinition(
                tool_id="hubspot.get_deals", source="function", mode="read_only",
                scopes=["crm.read"], enabled=True,
                meta={"description": "Get HubSpot deals"},
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
