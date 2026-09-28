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
    assert _attempt_write("kettle.prodeng-response.json").returncode == 0
