# Friday — Testing Playbook

_Maintained manually. Update when new test files or major suites are added._

---

## Quick Reference

```bash
# Run all tests (from repo root)
pytest tests/ -x -q

# Run a single file
pytest tests/test_smoke.py -v

# Run a specific test
pytest tests/test_okr_redesign.py::TestObjectiveProgressFromKeyResults -v

# Run with output (don't suppress print/logs)
pytest tests/ -s -q

# TypeScript type check (from apps/web/)
cd apps/web && npx tsc --noEmit

# Eval harness (integration, slow)
pytest tests/test_phase3.py::test_eval_harness_scores_core_routing -v
```

---

## Test Files

| File | Scope | What it covers |
|------|-------|----------------|
| `test_smoke.py` | Integration | Core orchestration — multi-specialist routing, approval gate, agent manifest presence |
| `test_phase2.py` | Integration | Memory persistence, web research routing, template responses, project charter flow |
| `test_phase3.py` | Integration | Workflow engine persistence, eval harness scoring, reflection report in chat result |
| `test_phase4.py` | Integration | MCP registry, tool registry, admin auth, specialist rule inheritance |
| `test_new_agents.py` | Unit/Integration | Routing correctness for AI Strategy, Internal Comms, PR, M&A, OKR Coach agents |
| `test_okr_redesign.py` | Unit | OKR hierarchy (3 levels), key result schema, initiative linking, progress from KRs, confidence scoring |
| `test_qa.py` | Unit | QA CRUD — test cases, suites, runs, bug reports, coverage analysis, registry summary |
| `test_workspaces.py` | Unit | Workspace create/retrieve, slug uniqueness, membership, entity linking, list filtering |
| `test_audit_store.py` | Unit | AuditLog SQLite persistence and reload |
| `test_tools_resources.py` | Unit | Tool docs retrieval with external resource catalog |
| `test_provenance.py` | Unit | Provenance question detection and answer building |
| `test_agent_project_manager.py` | Unit | Project manager manifest existence and routing |

---

## Regression Expectations

These behaviors must never regress. Run `test_smoke.py` before every push:

| Behavior | Test |
|----------|------|
| Multi-specialist routing (chief_of_staff + finance + operations + critic) | `test_manager_orchestrates_required_specialists` |
| Write scope triggers approval gate | `test_write_scope_triggers_approval_gate` |
| Agent architect manifest exists | `test_agent_manifests_include_agent_architect` |
| Project management requests route to project_manager | `test_project_management_requests_consult_project_manager` |
| OKR hierarchy (company → team → individual) | `TestObjectiveHierarchyThreeLevels` |
| OKR progress auto-computes from key results | `TestObjectiveProgressFromKeyResults` |
| Workspace slug uniqueness enforced | `TestWorkspaceSlugUniqueness` |
| Audit log persists and reloads across instances | `test_audit_log_persists_and_reloads_from_sqlite_store` |

---

## Evals (Separate from Unit Tests)

```bash
# Eval harness: runs structured scenario files
pytest tests/test_phase3.py::test_eval_harness_scores_core_routing -v
```

- **Eval scenarios:** `evals/scenarios/core-routing.json` — tests that the right agents are selected for business queries
- **Eval datasets:** `evals/datasets/` — graded examples for scoring
- **Harness class:** `workers/evals/harness.py` → `EvalHarness`
- Evals are slow (real LLM calls). Run them before merging structural orchestration changes.

---

## Coverage Areas — Always Regression-Test After Changes To

| You changed | Always run |
|-------------|-----------|
| `workers/orchestrator/runtime.py` | `test_smoke.py`, `test_phase3.py` |
| `packages/tools/policy_wrapped_tools.py` | `test_tools_resources.py`, `test_phase4.py` |
| `packages/agents/runtime.py` | `test_new_agents.py`, `test_smoke.py` |
| `packages/okrs/` | `test_okr_redesign.py` |
| `packages/workspaces/` | `test_workspaces.py` |
| `packages/governance/` | `test_smoke.py` (approval gate), `test_audit_store.py` |
| `packages/qa/` | `test_qa.py` |
| Any new agent manifest | `test_new_agents.py` (add routing test) |

---

## QA/Evals Live Here

| Location | Purpose |
|----------|---------|
| `tests/` | Pytest unit and integration tests |
| `evals/scenarios/core-routing.json` | Eval harness scenario for agent routing |
| `evals/datasets/` | Scored example inputs/outputs |
| `workers/evals/harness.py` | `EvalHarness` class |
| `workers/evals/worker.py` | Eval execution worker |
| `workers/reflection/worker.py` | `ReflectionWorker` — generates lesson candidates from `RunTrace` |

---

## TypeScript / Frontend

There is no frontend test suite yet. Type safety is the primary quality gate:

```bash
cd apps/web && npx tsc --noEmit
```

**Known pre-existing type error** (do not fix unless specifically tasked):
- `apps/web/app/qa/tests/new/page.tsx` — `release_blocker: boolean` not assignable to `Record<string, string>` index signature

All other type errors are regressions that should be fixed before pushing.

---

## Test Data Notes

- Tests that create services use `tmp_path` (pytest fixture) for isolated SQLite DBs
- Tests that call `FridayService()` directly use production DB paths — avoid for unit tests
- MCP registry tests use `tmp_path` to avoid polluting `data/mcp_servers.json`
