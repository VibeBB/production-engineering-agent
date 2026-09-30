from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

LAUNCHER_PATH = (
    Path(__file__).resolve().parents[1] / "plugins" / "prodeng" / "scripts" / "prodeng_launcher.py"
)


def _load_launcher() -> ModuleType:
    spec = importlib.util.spec_from_file_location("prodeng_launcher", LAUNCHER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fixed_image_ref(_root: Path) -> str:
    return "prodeng-tools:test"


def test_inspect_timeout_is_operation_specific_and_does_not_pull(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    launcher = _load_launcher()
    monkeypatch.setattr(launcher, "_docker", lambda: "docker")
    monkeypatch.setattr(launcher, "_image_from_lock", _fixed_image_ref)
    calls: list[list[str]] = []

    def timeout(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        assert kwargs["timeout"] == launcher._INSPECT_TIMEOUT_S
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(launcher.subprocess, "run", timeout)

    with pytest.raises(RuntimeError, match="docker image inspect timed out after 30 seconds"):
        launcher._ensure_image(tmp_path)

    assert len(calls) == 1
    assert calls[0][1:3] == ["image", "inspect"]


def test_pull_timeout_is_operation_specific(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    launcher = _load_launcher()
    monkeypatch.setattr(launcher, "_docker", lambda: "docker")
    monkeypatch.setattr(launcher, "_image_from_lock", _fixed_image_ref)

    def timeout(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if command[1:3] == ["image", "inspect"]:
            return subprocess.CompletedProcess(command, 1)
        assert kwargs["timeout"] == launcher._PULL_TIMEOUT_S
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(launcher.subprocess, "run", timeout)

    with pytest.raises(RuntimeError, match="docker pull timed out after 900 seconds"):
        launcher._ensure_image(tmp_path)


def test_docker_launcher_sets_workspace_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    launcher = _load_launcher()
    monkeypatch.setenv("OPENHANDS_PROJECT_DIR", str(tmp_path))

    argv = launcher._docker_argv("prodeng-tools:test", None, ["python", "-m", "prodeng.cli"])

    assert f"OPENHANDS_PROJECT_DIR={tmp_path}" in argv
