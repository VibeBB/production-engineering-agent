from __future__ import annotations

import asyncio
import importlib
import json
import shutil
import sys
from collections.abc import Coroutine
from pathlib import Path
from typing import Any, cast

import pytest
from mcp import types

EXAMPLE = Path(__file__).parents[1] / "examples" / "smart-kettle"


def _copy_example(directory: Path) -> Path:
    directory.mkdir(parents=True)
    shutil.copyfile(EXAMPLE / "smart-kettle.prodeng.json", directory / "smart-kettle.prodeng.json")
    shutil.copytree(EXAMPLE / "upstream", directory / "upstream")
    return directory / "smart-kettle.prodeng.json"


def _call_tool(mcp_server: Any, name: str, arguments: dict[str, Any]) -> types.CallToolResult:
    return asyncio.run(
        cast(Coroutine[Any, Any, types.CallToolResult], mcp_server.call_tool(name, arguments))
    )


def _text(result: types.CallToolResult) -> str:
    assert result.content
    content = result.content[0]
    assert isinstance(content, types.TextContent)
    return content.text


def test_cli_and_mcp_remain_usable_without_pillow(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setitem(sys.modules, "PIL", None)
    for module_name in ("prodeng.render", "prodeng.cli", "prodeng.mcp_server"):
        monkeypatch.delitem(sys.modules, module_name, raising=False)

    cli_module: Any = importlib.import_module("prodeng.cli")
    mcp_server: Any = importlib.import_module("prodeng.mcp_server")
    assert callable(cli_module.main)
    assert callable(mcp_server.call_tool)
    assert "prodeng.render" not in sys.modules

    workspace = tmp_path / "workspace"
    contract_path = _copy_example(workspace)
    monkeypatch.setenv("OPENHANDS_PROJECT_DIR", str(workspace))
    unavailable_text = "Pillow is not installed in this prodeng-tools image"

    mcp_author_dir = workspace / "mcp-author"
    mcp_author = _call_tool(
        mcp_server,
        "prodeng_author",
        {
            "contract_path": str(contract_path),
            "out_dir": str(mcp_author_dir),
            "render": True,
        },
    )
    assert mcp_author.isError is False
    mcp_author_payload = json.loads(_text(mcp_author))
    assert mcp_author_payload["verdict"] == "pass"
    assert unavailable_text in mcp_author_payload["render_skipped"]
    assert "vision_review_required" not in mcp_author_payload
    assert len(mcp_author.content) == 1
    assert mcp_author_payload["requests"]
    assert (mcp_author_dir / "control-plan.csv").is_file()
    assert (mcp_author_dir / "prodeng-report.json").is_file()

    mcp_render = _call_tool(
        mcp_server,
        "prodeng_render",
        {"contract_path": str(contract_path), "out_dir": str(workspace / "mcp-render")},
    )
    assert mcp_render.isError is True
    assert unavailable_text in _text(mcp_render)

    cli_author_dir = workspace / "cli-author"
    assert (
        cli_module.main(["author", str(contract_path), "--out", str(cli_author_dir), "--render"])
        == 0
    )
    cli_author_payload = json.loads(capsys.readouterr().out)
    assert cli_author_payload["verdict"] == "pass"
    assert unavailable_text in cli_author_payload["render_skipped"]
    assert "vision_review_required" not in cli_author_payload
    assert cli_author_payload["requests"]
    assert (cli_author_dir / "control-plan.csv").is_file()
    assert (cli_author_dir / "prodeng-report.json").is_file()

    assert cli_module.main(["render", str(contract_path)]) == 2
    cli_render_payload = json.loads(capsys.readouterr().out)
    assert cli_render_payload["verdict"] == "fail"
    assert unavailable_text in cli_render_payload["detail"]

    assert cli_module.main(["doctor"]) == 0
    doctor_payload = json.loads(capsys.readouterr().out)
    assert unavailable_text in doctor_payload["pillow"]
