from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path
from types import ModuleType
from typing import Any, TypedDict

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


class _ImagePin(TypedDict):
    ref: str
    image: str | None
    digest: str | None
    attestation: str | None


def _fixed_image_ref(_root: Path) -> _ImagePin:
    return {
        "ref": "prodeng-tools:test",
        "image": None,
        "digest": None,
        "attestation": None,
    }


def test_source_resolution_uses_prodeng_src(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    launcher = _load_launcher()
    source = tmp_path / "prodeng-src"
    package = source / "prodeng"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.setenv("PRODENG_SRC", str(source))
    monkeypatch.delenv("WIRE_SRC", raising=False)

    assert launcher.resolve_source(tmp_path / "plugins" / "prodeng") == source.resolve()


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


def test_docker_launcher_drops_capabilities_and_new_privileges(tmp_path: Path) -> None:
    launcher = _load_launcher()

    argv = launcher._docker_argv("prodeng-tools:test", None, ["python", "-m", "prodeng.cli"])

    assert argv[argv.index("--cap-drop") + 1] == "ALL"
    assert argv[argv.index("--security-opt") + 1] == "no-new-privileges"


def test_lock_entry_ref_preserves_attestation_metadata(tmp_path: Path) -> None:
    launcher = _load_launcher()
    lock = tmp_path / "image-digests.json"
    image = "ghcr.io/vibebb/prodeng-tools"
    digest = f"sha256:{'a' * 64}"
    attestation = "https://github.com/VibeBB/production-engineering-agent/attestations/example"
    lock.write_text(
        json.dumps(
            {
                "prodeng_tools": {
                    "image": image,
                    "digest": digest,
                    "attestation": attestation,
                }
            }
        ),
        encoding="utf-8",
    )

    assert launcher._lock_entry_ref(lock, "prodeng_tools") == {
        "ref": f"{image}@{digest}",
        "image": image,
        "digest": digest,
        "attestation": attestation,
    }
