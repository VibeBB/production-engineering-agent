from __future__ import annotations

import asyncio
import json
from collections.abc import Coroutine
from pathlib import Path
from typing import Any, cast

import pytest
from mcp import types

from prodeng import mcp_server


def _call_tool(name: str, arguments: dict[str, Any]) -> types.CallToolResult:
    return asyncio.run(
        cast(Coroutine[Any, Any, types.CallToolResult], mcp_server.call_tool(name, arguments))
    )


def _text(result: types.CallToolResult) -> str:
    assert result.content
    block = result.content[0]
    assert isinstance(block, types.TextContent)
    return block.text


def test_unknown_mcp_tool_returns_error_result() -> None:
    result = _call_tool("unknown_tool", {})

    assert result.isError is True
    assert _text(result) == json.dumps(
        {"verdict": "fail", "detail": "unknown tool unknown_tool"},
        indent=2,
        sort_keys=True,
    )


def test_raised_mcp_handler_returns_error_result(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail(_name: str, _arguments: dict[str, Any]) -> dict[str, object]:
        raise RuntimeError("handler exploded")

    monkeypatch.setattr(mcp_server, "dispatch_tool", fail)
    result = _call_tool("prodeng_doctor", {})

    assert result.isError is True
    assert _text(result) == json.dumps(
        {"verdict": "fail", "detail": "prodeng_doctor error: handler exploded"},
        indent=2,
        sort_keys=True,
    )


def test_gate_failure_payload_is_not_an_mcp_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def gate_failure(_name: str, _arguments: dict[str, Any]) -> dict[str, object]:
        return {"verdict": "fail", "detail": "gate failed"}

    monkeypatch.setattr(mcp_server, "dispatch_tool", gate_failure)
    result = _call_tool("prodeng_gates", {"contract_path": "contract.json"})

    assert result.isError is False
    assert json.loads(_text(result)) == {"verdict": "fail", "detail": "gate failed"}


def test_mcp_paths_resolve_relative_to_workspace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OPENHANDS_PROJECT_DIR", str(tmp_path))
    captured: dict[str, Any] = {}

    async def capture(_name: str, arguments: dict[str, Any]) -> dict[str, object]:
        captured.update(arguments)
        return {"verdict": "pass"}

    monkeypatch.setattr(mcp_server, "dispatch_tool", capture)
    result = _call_tool("prodeng_validate", {"contract_path": "contract.json"})

    assert result.isError is False
    assert captured["contract_path"] == str(tmp_path / "contract.json")


@pytest.mark.parametrize("path", ["../outside.json"])
def test_mcp_rejects_parent_traversal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, path: str
) -> None:
    monkeypatch.setenv("OPENHANDS_PROJECT_DIR", str(tmp_path))

    result = _call_tool("prodeng_validate", {"contract_path": path})

    assert result.isError is True
    assert "path is outside the workspace" in _text(result)


def test_mcp_rejects_absolute_path_outside_workspace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OPENHANDS_PROJECT_DIR", str(tmp_path))

    result = _call_tool(
        "prodeng_validate", {"contract_path": str(tmp_path.parent / "outside.json")}
    )

    assert result.isError is True
    assert "path is outside the workspace" in _text(result)


def test_mcp_rejects_symlinked_workspace_component(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OPENHANDS_PROJECT_DIR", str(tmp_path))
    outside = tmp_path.parent / "outside"
    outside.mkdir()
    (tmp_path / "link").symlink_to(outside, target_is_directory=True)

    result = _call_tool("prodeng_validate", {"contract_path": "link/contract.json"})

    assert result.isError is True
    assert "workspace path contains a symlink" in _text(result)
