# Update Repo Map

Regenerate the repo-map and agent-registry summary docs after structural changes.

Run:
```bash
python3 scripts/update_repo_map.py
```

Then confirm:
- `docs/repo-map.md` — updated route count, package list, and timestamp
- `docs/agent-registry-summary.md` — updated agent list and write-tool assignments

Use this after:
- Adding a new package to `packages/`
- Adding or removing an agent manifest
- Adding new API routes to `apps/api/main.py`
- Adding new frontend pages
- Adding new write tools to `policy_wrapped_tools.py`

Do **not** run this for every small code change — only after meaningful structural additions.
