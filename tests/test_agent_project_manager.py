from pathlib import Path

def test_project_manager_manifest_exists() -> None:
    path = Path(__file__).resolve().parents[1] / 'packages/agents/manifests/project_manager.json'
    assert path.exists()
