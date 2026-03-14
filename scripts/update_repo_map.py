#!/usr/bin/env python3
"""
update_repo_map.py — Regenerate docs/repo-map.md and docs/agent-registry-summary.md.

Run after meaningful structural changes:
    python scripts/update_repo_map.py

No heavy dependencies. Reads source files; writes deterministic markdown.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DOCS.mkdir(exist_ok=True)


# ── helpers ───────────────────────────────────────────────────────────────────

def _count_lines(path: Path) -> int:
    try:
        return sum(1 for _ in path.open())
    except OSError:
        return 0


def _route_paths(main_py: Path) -> list[str]:
    """Extract all @app.{method}("/path") decorators from main.py."""
    routes: list[str] = []
    try:
        for line in main_py.read_text().splitlines():
            stripped = line.strip()
            for method in ("get", "post", "put", "patch", "delete"):
                if stripped.startswith(f"@app.{method}("):
                    # Extract the path string
                    start = stripped.find('"')
                    if start == -1:
                        start = stripped.find("'")
                    if start != -1:
                        end = stripped.find('"', start + 1)
                        if end == -1:
                            end = stripped.find("'", start + 1)
                        if end != -1:
                            path_str = stripped[start + 1 : end]
                            routes.append(f"{method.upper():7} {path_str}")
    except OSError:
        pass
    return routes


def _package_summary(packages_dir: Path) -> list[tuple[str, str]]:
    """Return (package_name, one-line description) for each package."""
    DESCRIPTIONS: dict[str, str] = {
        "agents":        "Multi-agent framework: 23 specialist manifests, runtime, registry, prompt library",
        "analytics":     "KPI and chart service (Plotly integration)",
        "brand":         "Brand guidelines and asset management",
        "common":        "Shared dataclasses, models, and validation (ChatRequest, SpecialistMemo, RunTrace…)",
        "conversations": "Chat thread and message persistence (SQLite)",
        "credentials":   "Credential storage and retrieval (API keys, OAuth tokens)",
        "decisions":     "Decision tracking, outcome logging, and search",
        "docgen":        "Document generation: Word, PowerPoint, Excel, PDF",
        "events":        "In-process event bus for async messaging",
        "finance":       "Budget, invoice, and financial modeling services",
        "governance":    "Policy engine, approval flow, audit log, run store",
        "integrations":  "External connectors: Google, Jira, Confluence, HubSpot, Notion, Linear, Slack, Outlook",
        "interpreter":   "Sandboxed Python code execution",
        "llm":           "LLM provider abstraction (Anthropic, OpenAI) — create_llm_provider() factory",
        "meetings":      "Meeting notes and action-item tracking",
        "memory":        "Semantic/episodic memory with SQLite and Postgres (pgvector) backends",
        "notifications": "In-app notification system with unread count and polling",
        "observability": "Structured logging service",
        "okrs":          "OKR management: objectives, key results, initiatives, check-ins, grading",
        "org_context":   "Organizational structure and people context",
        "proactive":     "ProactiveScanner, MeetingBriefService, DigestService",
        "process":       "Process mapping, versioning, analytics, and SOP repository",
        "projects":      "Lightweight project tracking under workspaces",
        "qa":            "QA: test cases, suites, runs, bug tracking, coverage reports",
        "storage":       "File upload, download, and binary storage repository",
        "tasks":         "Task management with OKR/process linkage and overdue/due-soon queries",
        "templates":     "Template storage, retrieval, and seed loading",
        "tools":         "MCP registry, ToolRegistry, ToolExecutor (policy-wrapped tool dispatch)",
        "voice":         "Voice transcription service",
        "workspaces":    "Workspace isolation, membership, and context summaries",
    }
    result: list[tuple[str, str]] = []
    for pkg_dir in sorted(packages_dir.iterdir()):
        if pkg_dir.is_dir() and not pkg_dir.name.startswith("_"):
            desc = DESCRIPTIONS.get(pkg_dir.name, "(see package source)")
            result.append((pkg_dir.name, desc))
    return result


def _frontend_pages(web_dir: Path) -> list[str]:
    """Return sorted list of Next.js page routes."""
    app_dir = web_dir / "app"
    pages: list[str] = []
    for page in sorted(app_dir.rglob("page.tsx")):
        rel = page.parent.relative_to(app_dir)
        route = "/" + str(rel).replace("\\", "/")
        if route == "/.":
            route = "/"
        pages.append(route)
    return pages


def _agent_data(manifests_dir: Path) -> list[dict]:
    """Load all agent manifests and return structured data."""
    agents = []
    for mf in sorted(manifests_dir.glob("*.json")):
        try:
            d = json.loads(mf.read_text())
        except json.JSONDecodeError:
            continue
        tools = d.get("tools_allowed", [])
        write_tools = [t for t in tools if any(k in t for k in ("create", "update", "write", "log", "post"))]
        prompt_path = f"packages/agents/prompts/{mf.stem}.md"
        agents.append({
            "file": mf.stem,
            "name": d.get("name", mf.stem),
            "purpose": d.get("purpose", ""),
            "tools": tools,
            "write_tools": write_tools,
            "prompt": prompt_path,
            "risk": d.get("governance", {}).get("risk_level", "standard"),
        })
    return agents


# ── generators ────────────────────────────────────────────────────────────────

def generate_repo_map() -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = []

    lines += [
        "# Friday — Repo Map",
        f"_Last updated: {now} · Generated by `scripts/update_repo_map.py`_",
        "",
        "> **Claude sessions:** Read this before investigating code. It tells you where everything lives.",
        "",
    ]

    # Product summary
    lines += [
        "## Product Summary",
        "",
        "Friday is a manager-led multi-agent business OS built on Anthropic Claude.",
        "23 specialist agents are coordinated by a central orchestrator.",
        "FastAPI backend (Python 3.9+) + Next.js 14 frontend. SQLite by default; Postgres optional.",
        "",
    ]

    # Top-level directories
    lines += [
        "## Top-Level Directories",
        "",
        "| Directory | Purpose |",
        "|-----------|---------|",
        "| `apps/api/` | FastAPI backend — routes, service wiring, security |",
        "| `apps/web/` | Next.js 14 frontend — pages, components, hooks |",
        "| `packages/` | 28 domain packages (agents, memory, tools, okrs, tasks, …) |",
        "| `workers/` | Orchestrator, eval harness, reflection worker |",
        "| `scripts/` | Dev helpers, agent scaffolder, repo-map generator |",
        "| `tests/` | 12 pytest test files |",
        "| `evals/` | Eval scenarios and datasets |",
        "| `data/` | SQLite databases and uploaded files (gitignored) |",
        "| `infra/` | Docker-compose, Temporal config |",
        "| `docs/` | Architecture docs (you are here) |",
        "| `.claude/` | Claude Code launch configs and slash commands |",
        "",
    ]

    # Backend packages
    packages_dir = ROOT / "packages"
    pkg_summary = _package_summary(packages_dir)
    lines += [
        "## Backend Packages (`packages/`)",
        "",
        "| Package | Purpose |",
        "|---------|---------|",
    ]
    for name, desc in pkg_summary:
        lines.append(f"| `{name}` | {desc} |")
    lines.append("")

    # Orchestration entry points
    lines += [
        "## Orchestration Entry Points",
        "",
        "```",
        "apps/api/main.py                    FastAPI app — all 133+ HTTP routes",
        "apps/api/service.py                 FridayService — instantiates every sub-service",
        "workers/orchestrator/runtime.py     FridayManager.run() / run_streaming()",
        "workers/orchestrator/planner.py     Agent selection + tree-of-thought planning",
        "workers/orchestrator/synthesizer.py Response synthesis and citation",
        "packages/agents/runtime.py          Individual specialist execution (_run_with_llm)",
        "packages/tools/policy_wrapped_tools.py  ToolExecutor — all write tool dispatch",
        "packages/tools/registry.py          Tool definitions, modes, scopes",
        "packages/common/models.py           Shared dataclasses (ChatRequest, SpecialistMemo…)",
        "```",
        "",
    ]

    # API routes
    main_py = ROOT / "apps" / "api" / "main.py"
    routes = _route_paths(main_py)
    main_lines = _count_lines(main_py)
    lines += [
        f"## API Routes (`apps/api/main.py` — {main_lines} lines, {len(routes)} routes)",
        "",
        "```",
    ]
    for r in routes:
        lines.append(r)
    lines += ["```", ""]

    # Frontend pages
    web_dir = ROOT / "apps" / "web"
    pages = _frontend_pages(web_dir)
    lines += [
        "## Frontend Pages (`apps/web/app/`)",
        "",
        "| Route | Notes |",
        "|-------|-------|",
    ]
    PAGE_NOTES: dict[str, str] = {
        "/":                  "Chat (Workspace component, SSE streaming)",
        "/home":              "Inbox dashboard — tasks, approvals, alerts, decisions",
        "/tasks":             "Task list with status filter and inline cycle",
        "/okrs":              "OKR list and health summary",
        "/okrs/[id]":         "OKR detail — key results, check-ins, activity",
        "/processes":         "Process library with completeness rings",
        "/processes/[id]":    "Process detail — steps, diagram, SOP, history",
        "/documents":         "Generated document browser",
        "/analytics":         "KPI dashboards and charts",
        "/workspaces":        "Workspace listing",
        "/workspaces/[id]":   "Workspace detail — members, OKRs, projects",
        "/qa":                "QA dashboard",
        "/settings":          "User settings and integrations",
        "/settings/memory":   "Semantic memory browser",
    }
    for route in pages:
        note = PAGE_NOTES.get(route, "")
        lines.append(f"| `{route}` | {note} |")
    lines.append("")

    # Key frontend files
    lines += [
        "## Key Frontend Files",
        "",
        "| File | Purpose |",
        "|------|---------|",
        "| `apps/web/components/workspace.tsx` | Main chat UI — LeftRail, Transcript, Composer, RightRail |",
        "| `apps/web/components/page-shell.tsx` | Layout shell for all non-chat pages — NAV_ITEMS, breadcrumbs |",
        "| `apps/web/components/use-chat-state.ts` | Chat state, SSE parsing, thread persistence, send/stop |",
        "| `apps/web/components/markdown-message.tsx` | Markdown renderer with code highlighting |",
        "| `apps/web/components/mermaid-diagram.tsx` | Mermaid diagram renderer (browser-only, dynamic import) |",
        "| `apps/web/components/artifact-card.tsx` | Artifact preview card with download link |",
        "| `apps/web/components/command-palette.tsx` | Cmd+K command palette |",
        "| `apps/web/app/api/chat/route.ts` | Next.js proxy — SSE stream to Python backend |",
        "| `apps/web/app/globals.css` | All CSS — tokens, components, layout |",
        "",
    ]

    # Agent and prompt locations
    manifests_dir = ROOT / "packages" / "agents" / "manifests"
    n_agents = len(list(manifests_dir.glob("*.json")))
    lines += [
        "## Agent Locations",
        "",
        f"| Location | Contents |",
        "|----------|----------|",
        f"| `packages/agents/manifests/` | {n_agents} JSON manifests (agent_id, name, purpose, tools_allowed, governance) |",
        f"| `packages/agents/prompts/` | {n_agents} Markdown system prompts |",
        f"| `packages/agents/registry.py` | AgentRegistry — loads and indexes manifests |",
        f"| `packages/agents/runtime.py` | _run_with_llm() — specialist execution and tool_requests parsing |",
        "",
        "See `docs/agent-registry-summary.md` for per-agent details.",
        "",
    ]

    # Data / schema
    lines += [
        "## SQLite Databases (`data/`)",
        "",
        "| File | Service |",
        "|------|---------|",
        "| `friday_memory.sqlite3` | LayeredMemoryService (semantic + episodic) |",
        "| `friday_workflows.sqlite3` | InProcessWorkflowEngine |",
        "| `friday_audit.sqlite3` | AuditLog / SQLiteRunStore |",
        "| `friday_approvals.sqlite3` | ApprovalService |",
        "| `friday_processes.sqlite3` | ProcessService |",
        "| `friday_okrs.sqlite3` | OKRService |",
        "| `friday_analytics.sqlite3` | KPIService |",
        "| `friday_qa.sqlite3` | QAService |",
        "| `friday_workspaces.sqlite3` | WorkspaceService |",
        "| `friday_projects.sqlite3` | ProjectService |",
        "| `friday_finance.sqlite3` | InvoiceService + BudgetService |",
        "| `friday_brand.sqlite3` | BrandAssetService |",
        "| `friday_decisions.sqlite3` | DecisionLogService |",
        "| `friday_meetings.sqlite3` | MeetingService |",
        "| `friday_org_context.sqlite3` | OrgContextService |",
        "| `friday_proactive.sqlite3` | ProactiveScanner |",
        "| `friday_credentials.sqlite3` | CredentialService |",
        "| `friday_templates.sqlite3` | TemplateService |",
        "| `friday_files.sqlite3` | FileStorageService |",
        "| `friday_conversations.sqlite3` | ConversationService |",
        "| `friday_tasks.sqlite3` | TaskService |",
        "| `friday_notifications.sqlite3` | NotificationService |",
        "",
    ]

    # High-risk zones
    lines += [
        "## High-Risk / High-Complexity Zones",
        "",
        "| Zone | Why it's sensitive |",
        "|------|--------------------|",
        "| `workers/orchestrator/runtime.py` | Core orchestration — changes affect every agent call |",
        "| `packages/tools/policy_wrapped_tools.py` | All write tool dispatch — security boundary |",
        "| `packages/governance/policy.py` | Authorization policy engine |",
        "| `packages/agents/runtime.py` → `_OUTPUT_CONTRACT` | JSON schema enforced on every LLM call |",
        "| `workspace.tsx` → `parseSegments()` | Never modify — governs all chat output rendering |",
        "| `apps/api/main.py` → `/chat/stream` | SSE streaming path; both paths must stay equivalent |",
        "| `packages/memory/service.py` | Semantic recall injected into every request |",
        "",
    ]

    return "\n".join(lines)


def generate_agent_registry() -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    manifests_dir = ROOT / "packages" / "agents" / "manifests"
    agents = _agent_data(manifests_dir)

    lines: list[str] = [
        "# Friday — Agent Registry Summary",
        f"_Last updated: {now} · Generated by `scripts/update_repo_map.py`_",
        "",
        f"Friday has **{len(agents)} registered specialist agents**.",
        "All agents are invoked by `FridayManager` based on planner routing.",
        "Write access is limited to agents with explicit `tool_requests` instructions in their system prompt.",
        "",
        "| Agent | File | Purpose | Write Tools | Prompt |",
        "|-------|------|---------|-------------|--------|",
    ]

    for a in agents:
        write_str = ", ".join(a["write_tools"]) if a["write_tools"] else "—"
        purpose_short = a["purpose"][:70] + ("…" if len(a["purpose"]) > 70 else "")
        lines.append(
            f"| **{a['name']}** | `{a['file']}` | {purpose_short} | `{write_str}` | `{a['prompt']}` |"
        )

    lines += [
        "",
        "## Write-Capable Agents",
        "",
        "Only these agents have `tool_requests` write access enabled:",
        "",
    ]

    write_agents = [a for a in agents if a["write_tools"]]
    if write_agents:
        for a in write_agents:
            lines.append(f"### {a['name']} (`{a['file']}.json`)")
            lines.append(f"- **Purpose:** {a['purpose']}")
            lines.append(f"- **Write tools:** {', '.join(a['write_tools'])}")
            lines.append(f"- **All tools:** {', '.join(a['tools'])}")
            lines.append(f"- **Prompt:** `{a['prompt']}`")
            lines.append("")
    else:
        lines.append("_(None currently)_")
        lines.append("")

    lines += [
        "## Adding a New Agent",
        "",
        "```bash",
        "python scripts/create_agent_from_template.py",
        "```",
        "",
        "Then:",
        "1. Edit `packages/agents/manifests/<id>.json` — set purpose, tools_allowed, governance",
        "2. Edit `packages/agents/prompts/<id>.md` — write the system prompt",
        "3. If write tools needed: add to `tools_allowed` and add `tool_requests` instructions to prompt",
        "4. Run `python scripts/update_repo_map.py` to update this file",
        "",
        "## Governance Notes",
        "",
        "- All agent outputs pass through `PolicyEngine` before write execution",
        "- High-risk writes trigger `ApprovalService` before `ToolExecutor.run()`",
        "- `AuditLog` records every run with full `RunTrace` (inputs, memos, synthesis, write_actions)",
        "- `ReflectionWorker` generates lesson candidates from each `RunTrace`",
    ]

    return "\n".join(lines)


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("Friday repo-map generator")
    print(f"  Root: {ROOT}")

    # Generate repo-map.md
    repo_map_path = DOCS / "repo-map.md"
    content = generate_repo_map()
    repo_map_path.write_text(content)
    print(f"  ✓ {repo_map_path.relative_to(ROOT)}")

    # Generate agent-registry-summary.md
    agent_reg_path = DOCS / "agent-registry-summary.md"
    content = generate_agent_registry()
    agent_reg_path.write_text(content)
    print(f"  ✓ {agent_reg_path.relative_to(ROOT)}")

    print("Done. Re-read CLAUDE.md → docs/ before starting any task.")


if __name__ == "__main__":
    main()
