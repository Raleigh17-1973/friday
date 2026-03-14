# Architecture Audit

Perform a quick consistency audit of the Friday codebase against the memory docs.

## Check 1 — Package vs Service Wiring

Confirm every package in `packages/` is instantiated in `apps/api/service.py`:

```bash
ls packages/ | grep -v __pycache__ | grep -v __init__
grep "self\." apps/api/service.py | grep "Service\|Registry\|Engine\|Worker" | sort
```

Any package with a `service.py` that is NOT wired in `FridayService.__init__()` is a gap.

## Check 2 — Tool Registry vs ToolExecutor

Confirm every registered tool in `registry.py` has a dispatch handler in `policy_wrapped_tools.py`:

```bash
grep "tool_id=" packages/tools/registry.py | grep -oE '"[a-z_.]*"' | sort
grep "tool_name ==" packages/tools/policy_wrapped_tools.py | sort
grep "tool_name.startswith" packages/tools/policy_wrapped_tools.py | sort
```

## Check 3 — Agent Manifests vs Prompts

Every manifest should have a matching prompt:

```bash
ls packages/agents/manifests/ | sed 's/.json//'
ls packages/agents/prompts/ | sed 's/.md//'
```

Diff the two lists — any manifest without a prompt is incomplete.

## Check 4 — Nav Item Sync

Both nav components must have identical items (same hrefs, same order):

```bash
grep "href:" apps/web/components/workspace.tsx | grep -v "//"
grep "href:" apps/web/components/page-shell.tsx | grep -v "//"
```

## Check 5 — TypeScript Types

```bash
cd apps/web && npx tsc --noEmit 2>&1 | grep -v "qa/tests/new" | grep error
```

Zero errors expected (one known pre-existing QA error is acceptable).

## Check 6 — Smoke Tests

```bash
pytest tests/test_smoke.py -v -q
```

All 4 smoke tests must pass.

## After the Audit

If gaps are found, address them in priority order:
1. Unregistered tools (security gap)
2. Missing prompts (agent will fail at runtime)
3. Nav sync issues (broken navigation)
4. Type errors (potential runtime failures)
5. Service wiring gaps (features silently broken)
