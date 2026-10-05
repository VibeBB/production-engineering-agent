"""Plugin hooks protect generated requests but leave sibling responses editable."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = (
    Path(__file__).resolve().parents[1]
    / "plugins"
    / "prodeng"
    / "hooks"
    / "scripts"
    / "protect_generated.py"
)
REVIEW_AGENT = (
    Path(__file__).resolve().parents[1] / "plugins" / "prodeng" / "agents" / "prodeng-review.md"
)


def _attempt_write(path: str) -> subprocess.CompletedProcess[str]:
    payload = {
        "tool_name": "file_editor",
        "tool_input": {"command": "write", "path": path, "content": "generated"},
    }
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )


def test_generated_output_and_request_are_protected_but_response_is_not() -> None:
    assert _attempt_write("out/product/control-plan.csv").returncode == 2
    assert _attempt_write("kettle.prodeng-request.json").returncode == 2
    assert _attempt_write("liaison/request.ux-response.json").returncode == 2
    assert _attempt_write("observations/prodeng/decisions.jsonl").returncode == 2
    assert _attempt_write("observations/prodeng/impressions.jsonl").returncode == 2
    assert _attempt_write("observations/prodeng/vision-reviews.jsonl").returncode == 2
    assert _attempt_write("observations/prodeng/records-status.json").returncode == 2
    assert _attempt_write("kettle.prodeng-response.json").returncode == 0


def test_review_agent_has_view_only_visual_hooks() -> None:
    source = REVIEW_AGENT.read_text(encoding="utf-8")
    frontmatter = source.split("---", 2)[1]

    assert "  - file_editor" in frontmatter
    assert "  - VisionInspectTool" in frontmatter
    assert "  - ThinkTool" in frontmatter
    assert "mcp_config:" in frontmatter
    assert "  prodeng:" in frontmatter
    assert "matcher: file_editor|apply_patch|terminal" in frontmatter
    assert "name: protect-generated" in frontmatter
    assert "matcher: inspect_image_with_vision" in frontmatter
    assert "name: record-vision-tool-event" in frontmatter
    assert "matcher: file_editor" in frontmatter
    assert "name: record-image-observation" in frontmatter
    assert "`file_editor view`" in source
    assert "use `view` only" in source
    assert "The only writes you may make are VRP records" in " ".join(source.split())
