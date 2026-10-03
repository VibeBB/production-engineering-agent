from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts import check_dependency_updates

ROOT = check_dependency_updates.ROOT


def test_lynis_clone_pin_parsed() -> None:
    statuses = check_dependency_updates.check_git_clones(
        ROOT, list_remote_tags=lambda url: ["3.1.7"]
    )
    lynis = next(status for status in statuses if status.name == "CISOfy/lynis")
    assert lynis.current == "3.1.7"
    assert lynis.latest == "3.1.7"
    assert lynis.outdated is False


def test_git_clones_report_outdated_and_fetch_failed() -> None:
    statuses = check_dependency_updates.check_git_clones(
        ROOT, list_remote_tags=lambda url: ["3.1.7", "3.2.0"]
    )
    lynis = next(status for status in statuses if status.name == "CISOfy/lynis")
    assert lynis.latest == "3.2.0"
    assert lynis.outdated is True

    def failed_tags(url: str) -> list[str]:
        raise OSError(url)

    statuses = check_dependency_updates.check_git_clones(ROOT, list_remote_tags=failed_tags)
    lynis = next(status for status in statuses if status.name == "CISOfy/lynis")
    assert lynis.latest == "?"
    assert lynis.fetch_failed is True
    assert lynis.outdated is False


def test_json_report_counts_fetch_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    statuses = [
        check_dependency_updates.DependencyStatus(
            surface="test",
            name="available",
            current="1.0",
            latest="1.1",
            source="test",
            outdated=True,
        ),
        check_dependency_updates.DependencyStatus(
            surface="test",
            name="unknown",
            current="1.0",
            latest="?",
            source="test",
            outdated=False,
            fetch_failed=True,
        ),
    ]

    def fake_check(_root: Path) -> list[check_dependency_updates.DependencyStatus]:
        return statuses

    def fake_deferrals(_root: Path) -> list[check_dependency_updates.DependencyDeferral]:
        return []

    monkeypatch.setattr(check_dependency_updates, "check_dependency_updates", fake_check)
    monkeypatch.setattr(check_dependency_updates, "load_deferrals", fake_deferrals)
    output = tmp_path / "report.json"

    assert check_dependency_updates.main(["--repo-root", str(tmp_path), "--json", str(output)]) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["outdated_count"] == 1
    assert payload["unknown_count"] == 1
