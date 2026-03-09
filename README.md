# Friday

Friday is a manager-led multi-agent business operating system.

## Status
This repository now contains a Phase 1 + Phase 2 + early Phase 3 baseline aligned to the build brief:
- Manager orchestration runtime (`workers/orchestrator`)
- Structured output contracts (`packages/common/schemas.py`)
- Agent registry with specialist manifests (`packages/agents/manifests`)
- Core specialists included in orchestration path: strategist, finance, operations, critic
- Layered memory service (`packages/memory/service.py`)
- Durable SQLite-backed memory repository for semantic/episodic/candidate persistence (`packages/memory/repository.py`)
- Governance services: policy, approvals, audit (`packages/governance`)
- Agent-aware tool policy checks and read-only tool execution wrappers (`packages/tools/policy_wrapped_tools.py`)
- API surface scaffold (`apps/api/main.py`) with required endpoints
- Functional memory candidate promotion endpoint with approval-aware behavior (`POST /memories/candidates/promote`)
- In-process durable workflow engine with Temporal adapter surface (`workers/orchestrator/workflows.py`)
- Temporal workflow definitions and worker entrypoint for durable remote execution (`workers/orchestrator/temporal_definitions.py`, `scripts/run_temporal_worker.py`)
- Eval harness backed by scenario suites (`workers/evals/harness.py`, `evals/scenarios/core-routing.json`)
- Reflection worker producing governed lesson candidates (`workers/reflection/worker.py`)
- Audit trace persistence via pluggable run stores (SQLite default, Postgres when `FRIDAY_AUDIT_DATABASE_URL` is set)
- Phase 4 baseline: MCP server registry, admin dashboard/control endpoints, and API hardening middleware
- Agent scaffolding command (`scripts/create_agent_from_template.py`)
- Friday continuity artifacts (`friday_charter.md`, `friday_voice.md`, `friday_relationship_memory.md`, `friday_reflection_policy.md`, `friday_vows.yaml`)

## Monorepo Shape
- `apps/api`
- `apps/web`
- `workers/orchestrator`
- `workers/reflection`
- `workers/evals`
- `packages/agents`
- `packages/tools`
- `packages/memory`
- `packages/governance`
- `packages/common`
- `infra/temporal`
- `infra/docker`
- `docs/architecture`
- `evals/datasets`
- `evals/scenarios`
- `scripts`

## Local Test
```bash
PYTHONPATH=. python3 -m pytest -q
```

## FastAPI Runtime (when dependencies are installed)
```bash
PYTHONPATH=. uvicorn apps.api.main:app --reload
```

## One-Command Local Stack (API + Temporal Worker)
```bash
pip install -e .[phase3]
scripts/dev_up.sh
```

Services:
- API: `http://127.0.0.1:8000`
- Temporal UI: `http://127.0.0.1:8088`

Shutdown infra:
```bash
scripts/dev_down.sh
```

## Phase 4 Admin Controls
- Set `FRIDAY_ADMIN_API_KEY` to enable admin routes.
- Admin endpoints:
  - `GET /admin/dashboard`
  - `GET /admin/tools`
  - `POST /admin/tools/mcp/register`
  - `POST /admin/tools/mcp/{server_id}/enable`
  - `POST /admin/agents/{agent_id}/status`
