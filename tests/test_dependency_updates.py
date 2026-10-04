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


def test_repo_workflows_cover_all_pinned_external_sources() -> None:
    actions = {
        status.name
        for status in check_dependency_updates.check_github_actions(
            ROOT, list_remote_tags=lambda url: ["v1.0.0"]
        )
    }
    downloads = {
        status.name
        for status in check_dependency_updates.check_workflow_downloads(
            ROOT,
            fetch_json=lambda url: {"info": {"version": "1.30.1"}},
            list_remote_tags=lambda url: ["v1.0.0"],
        )
    }
    assert "github/codeql-action/upload-sarif" in actions
    assert {
        "rhysd/actionlint",
        "zizmor",
        "aquasecurity/trivy",
        "actionlint download checksum",
        "zizmor download checksum",
    } <= downloads


def test_subpath_action_pins_track_the_parent_repo(tmp_path: Path) -> None:
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "lint.yml").write_text(
        "steps:\n"
        "  - uses: github/codeql-action/upload-sarif@"
        "2892aa5e19bbd11bc0cff5427e3b750a04d9e3c2 # v4.38.2\n",
        encoding="utf-8",
    )
    seen: list[str] = []

    def remote_tags(url: str) -> list[str]:
        seen.append(url)
        return ["v4.38.2"]

    statuses = check_dependency_updates.check_github_actions(tmp_path, list_remote_tags=remote_tags)

    pin = next(status for status in statuses if status.name == "github/codeql-action/upload-sarif")
    assert pin.current == "v4.38.2"
    assert pin.latest == "v4.38.2"
    assert not pin.outdated
    assert seen == ["https://github.com/github/codeql-action"]


def test_workflow_download_pins_and_checksums(tmp_path: Path) -> None:
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "lint.yml").write_text(
        'tarball="actionlint_1.7.12_linux_amd64.tar.gz"\n'
        'curl "https://github.com/rhysd/actionlint/releases/download/v1.7.12/$tarball"\n'
        'echo "8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8'
        '  $RUNNER_TEMP/$tarball" | sha256sum -c -\n'
        'wheel="zizmor-1.30.1-py3-none-manylinux_2_28_x86_64.whl"\n'
        'echo "eee12266b793cb87ad4a7e3af2e72404f8a63e3de5eb099b80bf7b1cfd232a8e'
        '  $RUNNER_TEMP/$wheel" | sha256sum -c -\n'
        "      - uses: aquasecurity/trivy-action@ed142fd0673e97e23eac54620cfb913e5ce36c25\n"
        "        with:\n"
        "          version: v0.75.0\n",
        encoding="utf-8",
    )

    statuses = check_dependency_updates.check_workflow_downloads(
        tmp_path,
        fetch_json=lambda url: {"info": {"version": "99.0.0"}},
        list_remote_tags=lambda url: ["v99.0.0"],
    )

    by_name = {status.name: status for status in statuses}
    assert by_name["rhysd/actionlint"].current == "v1.7.12"
    assert by_name["rhysd/actionlint"].outdated is True
    assert by_name["zizmor"].current == "1.30.1"
    assert by_name["zizmor"].latest == "99.0.0"
    assert by_name["aquasecurity/trivy"].current == "v0.75.0"
    assert by_name["aquasecurity/trivy"].outdated is True
    assert by_name["actionlint download checksum"].outdated is False
    assert by_name["zizmor download checksum"].outdated is False


def test_workflow_download_checksum_must_be_sha256(tmp_path: Path) -> None:
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "lint.yml").write_text(
        'tarball="actionlint_1.7.12_linux_amd64.tar.gz"\n'
        'echo "deadbeef  $RUNNER_TEMP/$tarball" | sha256sum -c -\n',
        encoding="utf-8",
    )

    statuses = check_dependency_updates.check_workflow_downloads(
        tmp_path,
        fetch_json=lambda url: {"info": {"version": "1.0.0"}},
        list_remote_tags=lambda url: [],
    )

    checksum = next(status for status in statuses if status.name.endswith("checksum"))
    assert checksum.outdated is True
    assert checksum.latest == "invalid"


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
