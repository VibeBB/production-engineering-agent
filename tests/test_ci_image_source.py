from __future__ import annotations

from pathlib import Path


def test_runtime_dependency_changes_rebuild_tools_image_for_e2e() -> None:
    workflow = Path(__file__).parents[1] / ".github" / "workflows" / "ci.yml"
    contents = workflow.read_text(encoding="utf-8")

    assert r"grep -Eq '^(docker/|\.dockerignore$|pyproject\.toml$|uv\.lock$)'" in contents
