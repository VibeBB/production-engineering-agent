from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.update_image_digest_lock import update_lock

_ATTESTATION = "https://github.com/VibeBB/production-engineering-agent/attestations/example"


def _update(path: Path, *, attestation: str | None = None) -> bool:
    return update_lock(
        path,
        entry="prodeng_tools",
        image="ghcr.io/vibebb/prodeng-tools",
        tag=f"{'a' * 40}-tools",
        digest=f"sha256:{'b' * 64}",
        published_at="2026-10-01T00:00:00Z",
        workflow_run="https://github.com/VibeBB/production-engineering-agent/actions/runs/1",
        dockerfile="docker/prodeng-tools.Dockerfile",
        tools={"prodeng": "0.1.0"},
        attestation=attestation,
    )


def test_image_lock_records_optional_attestation(tmp_path: Path) -> None:
    lock = tmp_path / "image-digests.json"

    assert _update(lock, attestation=_ATTESTATION)
    assert not _update(lock, attestation=_ATTESTATION)
    entry = json.loads(lock.read_text(encoding="utf-8"))["prodeng_tools"]

    assert entry["attestation"] == _ATTESTATION


def test_image_lock_rejects_empty_attestation(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="attestation must not be empty"):
        _update(tmp_path / "image-digests.json", attestation="")
