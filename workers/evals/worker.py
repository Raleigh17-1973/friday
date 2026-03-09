from __future__ import annotations

from pathlib import Path

from workers.evals.harness import EvalHarness


def run_eval_suite(suite: str, manager, repo_root: Path | None = None) -> dict[str, object]:
    root = repo_root or Path(__file__).resolve().parents[2]
    harness = EvalHarness(root)
    report = harness.run_suite(suite, manager)
    return report.to_dict()
