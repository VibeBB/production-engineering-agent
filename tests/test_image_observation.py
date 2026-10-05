from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = (
    Path(__file__).resolve().parents[1]
    / "plugins"
    / "prodeng"
    / "hooks"
    / "scripts"
    / "record_image_observation.py"
)


@pytest.mark.parametrize("tool_name", ["prodeng_render", "prodeng_author"])
def test_render_tool_responses_record_observed_pngs(
    tmp_path: Path, tool_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENHANDS_PROJECT_DIR", str(tmp_path))
    image_path = tmp_path / "out" / "renders" / "control-plan.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"png bytes")
    payload = {
        "tool_name": tool_name,
        "tool_response": {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({"vision_review_required": [str(image_path)]}),
                }
            ]
        },
    }
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        check=False,
    )
    assert result.returncode == 0
    log = tmp_path / "observations" / "prodeng" / "image-observations.jsonl"
    observation = json.loads(log.read_text(encoding="utf-8"))
    assert observation["tool_name"] == tool_name
    assert observation["image_path"] == str(image_path)
    assert observation["image_sha256"] == hashlib.sha256(b"png bytes").hexdigest()
