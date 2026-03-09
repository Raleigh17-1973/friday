import json
from pathlib import Path

from packages.tools.policy_wrapped_tools import ToolExecutor


def test_docs_retrieve_includes_external_resources(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "data").mkdir(parents=True, exist_ok=True)

    local_doc = repo_root / "README.md"
    local_doc.write_text("local project docs", encoding="utf-8")

    external_doc = tmp_path / "external_notes.txt"
    external_doc.write_text("PMBOK schedule management and risk response guidance", encoding="utf-8")

    catalog = {
        "resources": [
            {
                "path": str(external_doc),
                "label": "PM resource",
                "domain": "project_management",
            }
        ]
    }
    (repo_root / "data" / "resource_catalog.json").write_text(json.dumps(catalog), encoding="utf-8")

    tool = ToolExecutor(repo_root)
    result = tool.run("docs.retrieve", {"query": "schedule management"})

    assert result.ok
    matches = result.output["matches"]
    assert matches
    assert any(item["path"] == str(external_doc) for item in matches)
