# Friday — Project Memory for Claude Sessions

## ⚡ Working Method for Future Claude Sessions

**Read this section first, every time.**

Before scanning the repository or reading individual files, consult these documents in order:

1. **This file** (`CLAUDE.md`) — product identity, architecture rules, coding conventions, command reference
2. **`docs/repo-map.md`** — directory map, key file locations, high-risk zones, last-updated timestamp
3. **`docs/agent-registry-summary.md`** — all 23 agents, their purposes, write access, and prompt paths
4. **`docs/testing-playbook.md`** — test commands, regression areas, eval harness

After reading those three files, you will know where to look for any specific task. **Do not scan the full repository from scratch.** Read only the files directly relevant to the current task.

> If the generated docs feel stale (e.g., a new package was added), run `python scripts/update_repo_map.py` to regenerate them, then re-read before working.

---

## Project Identity

**Friday** is a manager-led multi-agent business operating system built on Anthropic Claude. It helps companies run strategy, operations, and knowledge work through 23 specialist AI agents coordinated by a central orchestrator. The product ships as a FastAPI backend + Next.js 14 frontend with SQLite persistence (Postgres-ready).

**Repo:** `Raleigh17-1973/friday` · **Version:** 0.2.0 · **Python ≥ 3.9**

---

## Core Product Rules (Never Violate These)

1. **Agents produce memos, not side effects.** Specialists return `SpecialistMemo` objects. Write actions are dispatched *after synthesis* by `FridayManager.run()` via `ToolExecutor`, not by agents directly.
2. **Write access requires scoped tools.** Every structured write (OKR, process, task, decision) goes through `ToolExecutor` → `policy_wrapped_tools.py`. No service is called directly from agent prompts.
3. **`parseSegments()` in workspace.tsx is sacred.** Do not modify this function. Markdown rendering applies only inside `kind: "text"` segments.
4. **Governance gates apply to all write scopes.** Policy engine, approval flow, and audit log must remain in the request path for any write operation.
5. **SQLite is the default persistence layer.** Postgres paths exist but are opt-in via env vars (`FRIDAY_MEMORY_DATABASE_URL`, `FRIDAY_AUDIT_DATABASE_URL`). Never break SQLite compatibility.
6. **workspace_id is always optional.** Every service that accepts it must work correctly when it is `None`.
7. **Streaming and non-streaming paths must stay equivalent.** Both `/chat` and `/chat/stream` must produce the same logical response, including write_actions.
8. **Never modify OKR pages, workspace backend, or QA pages** unless the task explicitly requires it — these are complete and regression-tested.

---

## Architecture Principles

### Orchestration stack (read top-down)
```
apps/api/main.py            ← FastAPI routes, ChatPayload validation
apps/api/service.py         ← FridayService: instantiates all sub-services
workers/orchestrator/runtime.py  ← FridayManager.run() / run_streaming()
workers/orchestrator/planner.py  ← Agent selection, tree-of-thought planning
workers/orchestrator/synthesizer.py ← Response synthesis
packages/agents/runtime.py  ← Individual specialist execution (_run_with_llm)
packages/tools/policy_wrapped_tools.py ← ToolExecutor: all write tool dispatch
packages/tools/registry.py  ← Tool definitions and scopes
```

### Adding a new write tool
1. Add `_mytool_method(args)` to `ToolExecutor` in `policy_wrapped_tools.py`
2. Add dispatch in `run()`: `if tool_name.startswith("mytool."): return self._mytool_method(tool_name, args)`
3. Register in `registry.py` with mode, scopes, and description
4. Add to relevant agent manifest's `tools_allowed` list
5. Instruct the agent in its system prompt when to emit `tool_requests`

### Adding a new agent
Use `scripts/create_agent_from_template.py` — do not create manifests manually.

### Frontend data flow
```
use-chat-state.ts  ← state, SSE parsing, backend sync
  ↓ fetch("/api/chat")
apps/web/app/api/chat/route.ts  ← Next.js proxy → Python backend
  ↓ POST BACKEND_URL/chat/stream
apps/api/main.py  ← chat_stream endpoint
  ↓ FridayService.execute_chat_payload
```

---

## Key File / Folder Guide

| What you need | Where to look |
|---|---|
| FastAPI routes | `apps/api/main.py` |
| Service instantiation | `apps/api/service.py` |
| Orchestrator entry point | `workers/orchestrator/runtime.py` → `FridayManager.run()` |
| Agent manifests (23 JSON) | `packages/agents/manifests/` |
| Agent system prompts (23 MD) | `packages/agents/prompts/` |
| Write tool dispatch | `packages/tools/policy_wrapped_tools.py` |
| Tool registry | `packages/tools/registry.py` |
| Shared data models | `packages/common/models.py` |
| Memory service | `packages/memory/service.py` |
| Chat state (frontend) | `apps/web/components/use-chat-state.ts` |
| Main chat UI | `apps/web/components/workspace.tsx` |
| Non-chat page layout | `apps/web/components/page-shell.tsx` |
| Nav items (both navs) | `workspace.tsx` NAV_ITEMS + `page-shell.tsx` NAV_ITEMS (must stay in sync) |
| CSS tokens | `apps/web/app/globals.css` (vars: `--accent`, `--surface`, `--bg`, `--text`, `--border`, `--radius-s/m`, `--space-1..5`) |
| SQLite databases | `data/friday_*.sqlite3` |
| Evals / eval harness | `workers/evals/harness.py`, `evals/scenarios/` |
| Tests | `tests/` (12 files, pytest) |
| Dev startup | `.claude/launch.json` (api: 8000, web: 3000) |

---

## Important Commands

```bash
# Run the full stack (via Claude Code launch configs)
# Use .claude/launch.json: friday-api (port 8000), friday-web (port 3000)

# Python tests
cd friday && pytest tests/ -x -q

# Single test file
pytest tests/test_smoke.py -v

# TypeScript type check
cd apps/web && npx tsc --noEmit

# Install all optional dependencies
pip install -e ".[all]"

# Regenerate repo memory docs (run after meaningful structural changes)
python scripts/update_repo_map.py

# Create a new agent from template
python scripts/create_agent_from_template.py

# Start Temporal worker (optional, for durable workflows)
python scripts/run_temporal_worker.py
```

---

## Coding Conventions

### Python
- `from __future__ import annotations` at top of every file
- Services use SQLite with `sqlite3.Row` factory and `check_same_thread=False`
- Migration pattern: `try: conn.execute("ALTER TABLE x ADD COLUMN y"); except: pass`
- All service methods return dataclasses with `.to_dict()` → `asdict(self)`
- New packages: create `packages/mypkg/__init__.py` + `packages/mypkg/service.py`, wire in `apps/api/service.py`
- ToolExecutor methods return `ToolResult(tool_name, ok, output, error)`

### TypeScript / React
- All pages: `"use client"` directive + `PageShell` wrapper for non-chat pages
- `BACKEND = process.env.NEXT_PUBLIC_FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000"` in every page
- Fire-and-forget backend syncs: `.catch(() => undefined)`
- Nav changes: always update **both** `workspace.tsx` NAV_ITEMS and `page-shell.tsx` NAV_ITEMS
- No new `<style>` blocks in components — use `globals.css` with CSS variables

---

## Critical Invariants

- `SpecialistMemo.tool_requests` is executed post-synthesis, never mid-agent
- `_inject_recalled_context()` is called before planning on every request
- Both SSE streaming and fallback non-streaming paths must surface `write_actions`
- `ConversationService.add_message()` auto-creates threads — explicit `create_thread()` is optional
- `TaskService`, `NotificationService`, `ConversationService`, `ActivityService` are all SQLite-backed singletons in `FridayService`
- `ActivityService` auto-logs task create/update and OKR check-in events; never raises — fire-and-forget
- The `data/` directory is never committed to git (SQLite files are gitignored)

---

## Imported References

@docs/repo-map.md
@docs/agent-registry-summary.md
@docs/testing-playbook.md
