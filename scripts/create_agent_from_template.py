from __future__ import annotations

import json
from pathlib import Path


def create_agent_from_template(*, agent_id: str, name: str, purpose: str, owner: str) -> dict[str, str]:
    root = Path(__file__).resolve().parents[1]
    manifests_dir = root / "packages" / "agents" / "manifests"
    prompts_dir = root / "packages" / "agents" / "prompts"
    schemas_dir = root / "packages" / "agents" / "schemas"
    evals_dir = root / "evals" / "datasets"
    scenarios_dir = root / "evals" / "scenarios"

    manifests_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir.mkdir(parents=True, exist_ok=True)
    schemas_dir.mkdir(parents=True, exist_ok=True)
    evals_dir.mkdir(parents=True, exist_ok=True)
    scenarios_dir.mkdir(parents=True, exist_ok=True)

    prompt_path = prompts_dir / f"{agent_id}.md"
    manifest_path = manifests_dir / f"{agent_id}.json"
    tests_path = root / "tests" / f"test_agent_{agent_id}.py"
    eval_fixture_path = evals_dir / f"{agent_id}.jsonl"
    scenario_path = scenarios_dir / f"{agent_id}_examples.md"
    approval_policy_path = root / "packages" / "governance" / f"policy_{agent_id}.md"
    readme_path = root / "packages" / "agents" / f"README_{agent_id}.md"

    prompt_path.write_text(
        f"# {name}\n\nPurpose: {purpose}\n\nReturn schema-conformant JSON only.\n",
        encoding="utf-8",
    )

    manifest = {
        "id": agent_id,
        "name": name,
        "purpose": purpose,
        "trigger_conditions": ["Domain-specific request detected."],
        "anti_trigger_conditions": ["General response can be handled by Friday manager."],
        "tools_allowed": ["memory.search", "docs.retrieve"],
        "risk_level": "low",
        "system_prompt_path": str(prompt_path.relative_to(root)),
        "input_schema": "packages/agents/schemas/specialist_input.schema.json",
        "output_schema": "packages/agents/schemas/specialist_memo.schema.json",
        "eval_dataset_id": f"evals/datasets/{agent_id}.jsonl",
        "owner": owner,
        "status": "draft",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    tests_path.write_text(
        "from pathlib import Path\n\n"
        f"def test_{agent_id}_manifest_exists() -> None:\n"
        f"    path = Path(__file__).resolve().parents[1] / 'packages/agents/manifests/{agent_id}.json'\n"
        "    assert path.exists()\n",
        encoding="utf-8",
    )

    eval_fixture_path.write_text("", encoding="utf-8")
    scenario_path.write_text(
        f"# {name} Example Scenarios\n\n- Scenario 1: TODO\n- Scenario 2: TODO\n",
        encoding="utf-8",
    )
    approval_policy_path.write_text(
        f"# Approval Policy for {name}\n\n- Default mode: read-only\n- Writes require explicit approval gate\n",
        encoding="utf-8",
    )
    readme_path.write_text(
        f"# {name}\n\nOwner: {owner}\n\nPurpose: {purpose}\n",
        encoding="utf-8",
    )

    return {
        "prompt_file": str(prompt_path),
        "manifest": str(manifest_path),
        "tests": str(tests_path),
        "eval_fixtures": str(eval_fixture_path),
        "example_scenarios": str(scenario_path),
        "approval_policy": str(approval_policy_path),
        "readme": str(readme_path),
    }


if __name__ == "__main__":  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(description="Scaffold a Friday agent from template")
    parser.add_argument("--id", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--purpose", required=True)
    parser.add_argument("--owner", required=True)
    args = parser.parse_args()

    generated = create_agent_from_template(
        agent_id=args.id,
        name=args.name,
        purpose=args.purpose,
        owner=args.owner,
    )
    print(json.dumps(generated, indent=2))
