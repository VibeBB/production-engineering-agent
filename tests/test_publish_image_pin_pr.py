from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPOSITORY = f"VibeBB/{Path(__file__).parents[1].name}"
PR_URL = f"https://github.com/{REPOSITORY}/pull/123"
BRANCH = "bot/update-image-digests-test"


@pytest.fixture
def publish_pin_pr(tmp_path: Path) -> tuple[Path, dict[str, str], Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(
        """#!/usr/bin/env bash
set -eu
printf '%s\\n' "$*" >> "$GH_STUB_CALLS"
case "$1 $2" in
  "pr view")
    case "$GH_STUB_CASE" in
      merged) printf 'MERGED\\n' ;;
      closed) printf 'CLOSED\\n' ;;
      *) printf 'OPEN\\n' ;;
    esac
    ;;
  "workflow run")
    ;;
  "pr checks")
    check_call=$(grep -c '^pr checks ' "$GH_STUB_CALLS")
    case "$GH_STUB_CASE" in
      unreported-then-green)
        case "$check_call" in
          1)
            printf "Error: no checks reported on the '%s' branch\\n" \
              'bot/update-image-digests-test' >&2
            exit 1
            ;;
          2)
            printf "Error: no required checks reported on the '%s' branch\\n" \
              'bot/update-image-digests-test' >&2
            exit 1
            ;;
          3)
            printf '[{"name":"verify","state":"PENDING","bucket":"pending"}]\\n'
            exit 8
            ;;
          *)
            printf '[{"name":"verify","state":"SUCCESS","bucket":"pass"}]\\n'
            ;;
        esac
        ;;
      no-required-checks-always)
        printf "Error: no required checks reported on the '%s' branch\\n" \
          'bot/update-image-digests-test' >&2
        exit 1
        ;;
      unexpected-check-error)
        printf 'stub transport error: permission denied\\n' >&2
        exit 1
        ;;
      required-failure)
        printf '[{"name":"verify","state":"FAILURE","bucket":"fail"}]\\n'
        ;;
      action-required)
        printf '[{"name":"verify","state":"ACTION_REQUIRED","bucket":null}]\\n'
        ;;
      pending-timeout)
        printf '[{"name":"verify","state":"PENDING","bucket":"pending"}]\\n'
        ;;
      *)
        printf '[{"name":"verify","state":"SUCCESS","bucket":"pass"}]\\n'
        ;;
    esac
    ;;
  "pr merge")
    ;;
  api\\ *)
    if [[ "$*" == *"-X POST"*"/approve"* ]]; then
      printf 'approval response noise\\n'
    else
      printf '77\\n'
    fi
    ;;
esac
""",
        encoding="utf-8",
    )
    gh.chmod(0o755)
    summary = tmp_path / "summary.md"
    calls = tmp_path / "calls.log"
    env = os.environ.copy()
    # A BASH_ENV-exported gh() shell function would shadow the PATH stub
    # inside the script under test (verify_all runs with one set).
    env.pop("BASH_ENV", None)
    env = {key: value for key, value in env.items() if not key.startswith("BASH_FUNC_gh")}
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "GITHUB_REPOSITORY": REPOSITORY,
            "GITHUB_STEP_SUMMARY": str(summary),
            "GH_STUB_CALLS": str(calls),
            "PUBLISH_PIN_PR_REQUIRED_WAIT_ATTEMPTS": "1",
            "PUBLISH_PIN_PR_REQUIRED_WAIT_SECONDS": "0",
            "PUBLISH_PIN_PR_MERGE_WAIT_ATTEMPTS": "1",
            "PUBLISH_PIN_PR_MERGE_WAIT_SECONDS": "0",
            "PUBLISH_PIN_PR_RETRY_ATTEMPTS": "1",
            "PUBLISH_PIN_PR_RETRY_DELAY_SECONDS": "0",
            "PUBLISH_PIN_PR_POST_MERGE_WORKFLOWS": "ci.yml locked-image-check.yml",
        }
    )
    return Path(__file__).parents[1] / "scripts/publish_image_pin_pr.sh", env, calls


def run_helper(script: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(script), PR_URL, BRANCH, "", "ci.yml locked-image-check.yml"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


@pytest.mark.parametrize(
    ("case", "returncode", "expected_summary"),
    [
        ("merged", 0, "is merged; dispatching"),
        ("closed", 1, "was closed without being merged"),
        ("action-required", 0, "auto-merge armed; required checks still running"),
        ("pending-timeout", 0, "auto-merge armed; required checks still running"),
        ("required-failure", 1, "A required check concluded non-success"),
    ],
)
def test_pin_pr_state_and_required_checks(
    publish_pin_pr: tuple[Path, dict[str, str], Path],
    tmp_path: Path,
    case: str,
    returncode: int,
    expected_summary: str,
) -> None:
    script, env, calls = publish_pin_pr
    env["GH_STUB_CASE"] = case
    result = run_helper(script, env)
    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    call_log = calls.read_text(encoding="utf-8")

    assert result.returncode == returncode
    assert expected_summary in summary
    assert "--json state,mergedAt" in call_log
    print(f"{case}: exit={result.returncode}")
    if result.stdout:
        print(f"stdout:\n{result.stdout.rstrip()}")
    if result.stderr:
        print(f"stderr:\n{result.stderr.rstrip()}")
    print(f"summary:\n{summary.rstrip()}")
    if case == "merged":
        assert f"workflow run ci.yml --repo {REPOSITORY} --ref main" in call_log
        assert f"--ref {BRANCH}" not in call_log
        # The post-merge run verifies the pin that just merged: the locked
        # pull path verifies it without a full image build.
        assert "-f docker_changed=locked" in call_log
    if case == "closed":
        assert "workflow run" not in call_log
    if case in ("action-required", "pending-timeout"):
        assert "--required --json name,state,bucket" in call_log
        assert "--auto --squash --delete-branch" in call_log
        assert "approval response noise" not in result.stdout + result.stderr
    if case == "action-required":
        assert "api -X POST repos/" in call_log
    if case == "required-failure":
        assert "--auto --squash --delete-branch" not in call_log


def test_unreported_checks_transition_to_green_json(
    publish_pin_pr: tuple[Path, dict[str, str], Path],
    tmp_path: Path,
) -> None:
    script, env, calls = publish_pin_pr
    env.update(
        {
            "GH_STUB_CASE": "unreported-then-green",
            "PUBLISH_PIN_PR_REQUIRED_WAIT_ATTEMPTS": "4",
        }
    )

    result = run_helper(script, env)
    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    call_log = calls.read_text(encoding="utf-8")

    assert result.returncode == 0
    assert call_log.count("pr checks ") == 5
    assert "--auto --squash --delete-branch" in call_log
    assert "--squash --delete-branch" in call_log
    assert "Auto-merge remains armed" in summary
    assert "no checks reported" not in result.stderr
    assert "no required checks reported" not in result.stderr


def test_no_required_checks_arms_auto_merge(
    publish_pin_pr: tuple[Path, dict[str, str], Path],
    tmp_path: Path,
) -> None:
    script, env, calls = publish_pin_pr
    env["GH_STUB_CASE"] = "no-required-checks-always"

    result = run_helper(script, env)
    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    call_log = calls.read_text(encoding="utf-8")

    assert result.returncode == 0
    assert "auto-merge armed; required checks still running" in summary
    assert call_log.count("pr checks ") == 1
    assert "--auto --squash --delete-branch" in call_log


def test_unexpected_required_check_error_fails_with_stderr(
    publish_pin_pr: tuple[Path, dict[str, str], Path],
) -> None:
    script, env, calls = publish_pin_pr
    env["GH_STUB_CASE"] = "unexpected-check-error"

    result = run_helper(script, env)

    assert result.returncode == 1
    assert (
        f"::error::Could not determine required checks for pin PR {PR_URL}: "
        "stub transport error: permission denied"
    ) in result.stderr
    assert calls.read_text(encoding="utf-8").count("pr checks ") == 1


def test_non_empty_base_sha_is_not_forwarded_to_dispatch(
    publish_pin_pr: tuple[Path, dict[str, str], Path],
) -> None:
    """ci.yml's workflow_dispatch inputs are only ref + docker_changed; a
    '-f base_sha' flag would 422. BASE_SHA stays accepted on argv for
    interface compat but is never forwarded."""
    script, env, calls = publish_pin_pr
    env["GH_STUB_CASE"] = "merged"

    result = subprocess.run(
        ["bash", str(script), PR_URL, BRANCH, "deadbeef" * 5, "ci.yml locked-image-check.yml"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    call_log = calls.read_text(encoding="utf-8")

    assert result.returncode == 0
    assert "-f base_sha" not in call_log
    assert "-f docker_changed=locked" in call_log


def test_publish_workflow_uses_pin_helper_and_sbom_guard() -> None:
    root = Path(__file__).parents[1]
    workflows = list((root / ".github/workflows").glob("publish-*-images.yml"))
    assert len(workflows) == 1
    workflow = workflows[0].read_text(encoding="utf-8")
    helper = (root / "scripts/publish_image_pin_pr.sh").read_text(encoding="utf-8")

    assert "scripts/publish_image_pin_pr.sh" in workflow
    assert "timeout-minutes: 120" in workflow
    assert "REQUIRED_WAIT_ATTEMPTS=" in helper and ":-60}" in helper
    assert "REQUIRED_WAIT_SECONDS=" in helper and ":-15}" in helper
    assert 'gh pr checks "$PR_URL" --repo "$GITHUB_REPOSITORY" --required' in helper
    # Syft pulls from the registry on publish and from the local docker
    # daemon under a dry_run rehearsal.
    assert (
        "SYFT_SOURCE_IMAGE_DEFAULT_PULL_SOURCE: "
        "${{ inputs.dry_run == true && 'docker' || 'registry' }}" in workflow
    )
    assert "TMPDIR: ${{ runner.temp }}" in workflow
    assert "SYFT_FILE_METADATA_SELECTION: none" in workflow
    assert "Guard tools SPDX SBOM size" in workflow
    generate = workflow.index("Generate tools SPDX SBOM")
    guard = workflow.index("Guard tools SPDX SBOM size")
    validate = workflow.index("Validate tools SPDX SBOM")
    assert generate < guard < validate
    assert 'df -h /tmp "$RUNNER_TEMP"' in workflow
    assert "16777216" in workflow


def test_publish_dry_run_skips_only_irreversible_steps() -> None:
    workflow = (
        Path(__file__).parents[1] / ".github/workflows/publish-prodeng-images.yml"
    ).read_text(encoding="utf-8")
    assert "      dry_run:\n        description:" in workflow
    for name in (
        "Promote :latest",
        "Attest tools image provenance",
        "Attest tools SBOM",
        "Update digest lock and merge PR",
    ):
        step = workflow.split(f"      - name: {name}\n", 1)[1].split("      - name:", 1)[0]
        assert "if: inputs.dry_run != true" in step, name
    assert "push: ${{ inputs.dry_run != true }}" in workflow
    assert "load: ${{ inputs.dry_run }}" in workflow
    sarif = workflow.split("      - name: Upload Trivy SARIF\n", 1)[1].split("      - name:", 1)[0]
    assert "inputs.dry_run != true" in sarif
    # The gate chain still runs: Trivy scans, SBOM generation, measurement,
    # and the container smoke carry no dry_run skip.
    for name in (
        "Scan tools image (Trivy SARIF)",
        "Scan tools image (Trivy JSON)",
        "Generate tools SPDX SBOM",
        "Measure published tools",
        "Verify published tools smoke",
    ):
        step = workflow.split(f"      - name: {name}\n", 1)[1].split("      - name:", 1)[0]
        assert "inputs.dry_run != true" not in step, name
    # Both Trivy scans must resolve through the dry_run-aware scan-ref
    # (a third use wires it into the TOOLS_REF env).
    assert workflow.count("${{ steps.scan-ref.outputs.ref }}") >= 2
