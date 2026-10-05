from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
from collections.abc import Coroutine
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from mcp import types
from pydantic import ValidationError

from prodeng import mcp_server, records
from prodeng.cli import main
from prodeng.ux_liaison import (
    ResponseStatus,
    TargetAgent,
    UxRequestV2,
    UxRespondInput,
    UxResponseV2,
    ux_inbox,
    ux_respond,
)

EXAMPLE = Path(__file__).parents[1] / "examples" / "smart-kettle"
LONG_IMPRESSION = (
    "The manufacturing handoff keeps the contract and station requirements visible for the team. "
    "The measured artifacts are bound to the current request inputs so a reader can check the "
    "basis for this response. The remaining uncertainty is whether every operator can follow the "
    "same reaction when an inspection result falls outside its limit. A production supervisor "
    "should confirm the station sequence and escalation path with operators before release. "
    "The next revision should capture any mismatch found during that pilot and regenerate the "
    "bound projections so the work instructions remain synchronized with the approved contract."
)
DECISION_RATIONALE = (
    "The selected station split keeps the combined cycle within the available takt "
    "while preserving "
    "a controlled inspection before downstream assembly. The alternative would leave excess work "
    "at the press operation and create a sustained queue. The additional handoff is manageable "
    "because the lot and operation identifiers remain visible to both stations."
)


def _input_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _request_payload(
    root: Path,
    request_id: str,
    *,
    target: str = "prodeng",
    risk: str = "low",
    rationale: str = "Coordinate production readiness with the design team.",
    depends_on: list[str] | None = None,
    input_path: str = "input.txt",
) -> dict[str, Any]:
    bound = root / input_path
    bound.parent.mkdir(parents=True, exist_ok=True)
    if not bound.exists():
        bound.write_text("current input\n", encoding="utf-8")
    return {
        "schema_version": 2,
        "system": "ux-creator",
        "id": request_id,
        "target_agent": target,
        "stage": "manufacturing_handoff",
        "risk": risk,
        "purpose": "Coordinate the manufacturing plan with the UX design.",
        "rationale": rationale,
        "requested_changes": ["Review the production work sequence."],
        "inputs": [{"path": input_path, "sha256": _input_hash(bound)}],
        "expected_deliverables": ["Approved work sequence"],
        "acceptance": ["The station instructions match the approved contract."],
        "depends_on": depends_on or [],
        "created_at": datetime.now(UTC).isoformat(),
    }


def _write_request(
    root: Path,
    request_id: str,
    **kwargs: Any,
) -> Path:
    return _write_request_payload(root, request_id, _request_payload(root, request_id, **kwargs))


def _write_request_payload(
    root: Path,
    request_id: str,
    payload: dict[str, Any],
) -> Path:
    directory = root / "liaison"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{request_id}.ux-request.json"
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _write_response(
    root: Path,
    request_id: str,
    *,
    responder: TargetAgent = "prodeng",
    status: ResponseStatus = "accepted",
    input_hashes: dict[str, str] | None = None,
) -> Path:
    directory = root / "liaison"
    directory.mkdir(parents=True, exist_ok=True)
    response = UxResponseV2(
        schema_version=2,
        system="ux-creator",
        request=request_id,
        responder=responder,
        status=status,
        reason="Completed a review of the current production request.",
        input_hashes=input_hashes or {},
        responded_at=datetime.now(UTC),
    )
    path = directory / f"{request_id}.ux-response.json"
    path.write_text(
        json.dumps(response.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _copy_example(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    contract_path = root / "smart-kettle.prodeng.json"
    shutil.copyfile(EXAMPLE / contract_path.name, contract_path)
    shutil.copytree(EXAMPLE / "upstream", root / "upstream")
    return contract_path


def _write_real_records(root: Path) -> tuple[str, str]:
    artifact = root / "artifact.txt"
    artifact.write_text("approved manufacturing handoff\n", encoding="utf-8")
    decision = records.record_decision(
        {
            "id": "line-balance-split",
            "stage": "contract",
            "question": "How should press and inspection work be divided across stations?",
            "principles": [
                "Takt time is the maximum sustainable interval between completed units.",
                "An inspection must detect a defect before it reaches the next operation.",
            ],
            "options": [
                {"name": "single", "pros": ["simple"], "cons": ["cycle exceeds takt"]},
                {"name": "split", "pros": ["balanced"], "cons": ["extra handoff"]},
            ],
            "chosen": "split",
            "rationale": DECISION_RATIONALE,
            "evidence": [{"path": "artifact.txt"}],
            "risks": ["The new handoff may lose lot traceability."],
            "revisit_when": "The production time study exceeds takt.",
        },
        root,
    )
    impression = records.record_impression(
        {
            "stage": "handoff",
            "artifacts": ["artifact.txt"],
            "impression": LONG_IMPRESSION,
        },
        root,
    )
    return decision["record"]["event_id"], impression["record"]["event_id"]


def _call_tool(name: str, arguments: dict[str, Any]) -> types.CallToolResult:
    return asyncio.run(
        cast(Coroutine[Any, Any, types.CallToolResult], mcp_server.call_tool(name, arguments))
    )


def _tool_json(result: types.CallToolResult) -> dict[str, Any]:
    assert result.content
    text = result.content[0]
    assert isinstance(text, types.TextContent)
    return json.loads(text.text)


def test_request_and_response_models_are_strict_and_timezone_aware(tmp_path: Path) -> None:
    high_risk = _request_payload(
        tmp_path,
        "high-risk",
        risk="high",
        rationale="Job boil requires an accessible single-hand opening action.",
    )
    request = UxRequestV2.model_validate_json(json.dumps(high_risk))
    assert request.id == "high-risk"

    with pytest.raises(ValidationError, match="job id"):
        UxRequestV2.model_validate_json(
            json.dumps(high_risk | {"rationale": "A high-risk request without a job citation."})
        )
    with pytest.raises(ValidationError, match="timezone"):
        UxRequestV2.model_validate_json(
            json.dumps(high_risk | {"created_at": "2026-02-02T00:00:00"})
        )
    with pytest.raises(ValidationError, match="Extra inputs"):
        UxRequestV2.model_validate_json(json.dumps(high_risk | {"unexpected": True}))

    response = UxResponseV2(
        schema_version=2,
        system="ux-creator",
        request="high-risk",
        responder="prodeng",
        status="accepted",
        input_hashes={"input.txt": "a" * 64},
        responded_at=datetime.now(UTC),
    )
    with pytest.raises(ValidationError, match="timezone"):
        UxResponseV2.model_validate_json(
            json.dumps(response.model_dump(mode="json") | {"responded_at": "2026-02-02T00:00:00"})
        )


def test_inbox_ignores_other_targets_and_reports_malformed_files(tmp_path: Path) -> None:
    empty = ux_inbox(tmp_path)
    assert empty == {
        "verdict": "pass",
        "requests": [],
        "malformed": [],
        "counts": {"new": 0, "stale": 0, "answered": 0, "blocked": 0},
    }
    _write_request(tmp_path, "other-target", target="wire")
    high_risk = _request_payload(
        tmp_path,
        "missing-job",
        risk="high",
        rationale="The request has no UX job identifier.",
    )
    (tmp_path / "liaison" / "missing-job.ux-request.json").write_text(
        json.dumps(high_risk), encoding="utf-8"
    )
    wrong_stem = _request_payload(tmp_path, "different-id")
    (tmp_path / "liaison" / "wrong-stem.ux-request.json").write_text(
        json.dumps(wrong_stem), encoding="utf-8"
    )
    (tmp_path / "liaison" / "bad.ux-response.json").write_text("{", encoding="utf-8")
    mismatched_response = UxResponseV2(
        schema_version=2,
        system="ux-creator",
        request="different-id",
        responder="prodeng",
        status="accepted",
        input_hashes={},
        responded_at=datetime.now(UTC),
    )
    (tmp_path / "liaison" / "mismatched.ux-response.json").write_text(
        mismatched_response.model_dump_json(), encoding="utf-8"
    )

    result = ux_inbox(tmp_path)

    assert result["requests"] == []
    assert result["counts"] == {"new": 0, "stale": 0, "answered": 0, "blocked": 0}
    malformed = cast(list[dict[str, str]], result["malformed"])
    assert {item["path"] for item in malformed} == {
        "liaison/missing-job.ux-request.json",
        "liaison/wrong-stem.ux-request.json",
        "liaison/bad.ux-response.json",
        "liaison/mismatched.ux-response.json",
    }


def test_high_risk_request_cites_a_declared_ux_job_when_available(tmp_path: Path) -> None:
    ux_contract = tmp_path / "ux-contract.json"
    ux_contract.write_text(json.dumps({"jobs": [{"id": "boil"}]}), encoding="utf-8")
    good = _request_payload(
        tmp_path,
        "good-job",
        risk="high",
        rationale="Job boil needs a reachable one-hand interaction.",
        input_path="ux-contract.json",
    )
    bad = _request_payload(
        tmp_path,
        "bad-job",
        risk="high",
        rationale="Job clean needs a different screen flow.",
        input_path="ux-contract.json",
    )
    for request_id, payload in (("good-job", good), ("bad-job", bad)):
        _write_request_payload(tmp_path, request_id, payload)

    result = ux_inbox(tmp_path)

    requests = cast(list[dict[str, object]], result["requests"])
    assert [item["id"] for item in requests] == ["good-job"]
    malformed = result["malformed"]
    assert isinstance(malformed, list)
    assert malformed[0]["path"] == "liaison/bad-job.ux-request.json"
    assert "declared UX job id" in malformed[0]["error"]


def test_inbox_states_staleness_precedence_and_dependencies(tmp_path: Path) -> None:
    answered_path = _write_request(
        tmp_path,
        "answered",
        depends_on=["open-dependency"],
        input_path="answered-input.txt",
    )
    current = json.loads(answered_path.read_text(encoding="utf-8"))["inputs"][0]["sha256"]
    _write_response(
        tmp_path,
        "answered",
        input_hashes={"answered-input.txt": current},
    )
    _write_request(
        tmp_path,
        "blocked",
        depends_on=["open-dependency"],
        input_path="blocked-input.txt",
    )
    _write_request(tmp_path, "dependency", input_path="dependency-input.txt")
    _write_response(tmp_path, "dependency", responder="circuit", status="done")
    _write_request(tmp_path, "new-request", input_path="new-input.txt")
    _write_request(tmp_path, "stale-response", input_path="stale-response-input.txt")
    _write_response(
        tmp_path,
        "stale-response",
        input_hashes={"stale-response-input.txt": "0" * 64},
    )
    _write_request(tmp_path, "stale-input", input_path="stale-input.txt")
    _write_request(tmp_path, "missing-input", input_path="missing-input.txt")
    (tmp_path / "stale-input.txt").write_text("changed input\n", encoding="utf-8")
    (tmp_path / "missing-input.txt").unlink()

    result = ux_inbox(tmp_path)
    requests = cast(list[dict[str, object]], result["requests"])
    states = {cast(str, item["id"]): cast(str, item["state"]) for item in requests}
    assert states == {
        "answered": "answered",
        "blocked": "blocked",
        "dependency": "new",
        "new-request": "new",
        "missing-input": "stale",
        "stale-input": "stale",
        "stale-response": "stale",
    }
    assert result["counts"] == {"new": 2, "stale": 3, "answered": 1, "blocked": 1}


def test_directory_input_hash_changes_mark_request_stale(tmp_path: Path) -> None:
    input_directory = tmp_path / "input-tree"
    input_directory.mkdir()
    child = input_directory / "source.json"
    child.write_text('{"revision": 1}\n', encoding="utf-8")
    payload = _request_payload(tmp_path, "tree-input")
    payload["inputs"] = [{"path": "input-tree", "sha256": records.tree_sha256(input_directory)}]
    _write_request_payload(tmp_path, "tree-input", payload)

    before = ux_inbox(tmp_path)
    requests = before["requests"]
    assert isinstance(requests, list)
    assert requests[0]["state"] == "new"
    child.write_text('{"revision": 2}\n', encoding="utf-8")
    after = ux_inbox(tmp_path)
    stale_requests = after["requests"]
    assert isinstance(stale_requests, list)
    assert stale_requests[0]["state"] == "stale"


def test_respond_writes_current_hashes_and_rejects_blocked_or_symlink_paths(
    tmp_path: Path,
) -> None:
    _write_request(tmp_path, "accepted")
    result = ux_respond({"request": "accepted", "status": "accepted"}, tmp_path)
    response_path = tmp_path / "liaison" / "accepted.ux-response.json"
    serialized = response_path.read_text(encoding="utf-8")
    payload = json.loads(serialized)
    assert serialized.endswith("\n")
    assert list(payload) == sorted(payload)
    assert payload["input_hashes"] == {"input.txt": _input_hash(tmp_path / "input.txt")}
    assert result["path"] == "liaison/accepted.ux-response.json"
    assert not list((tmp_path / "liaison").glob("*.tmp"))

    artifact_directory = tmp_path / "artifact-directory"
    artifact_directory.mkdir()
    (artifact_directory / "result.json").write_text("{}\n", encoding="utf-8")
    _write_request(tmp_path, "directory-artifact")
    directory_response = ux_respond(
        {
            "request": "directory-artifact",
            "status": "accepted",
            "artifacts": ["artifact-directory"],
        },
        tmp_path,
    )
    directory_response_body = directory_response["response"]
    assert isinstance(directory_response_body, dict)
    assert directory_response_body["artifacts"] == [
        {
            "path": "artifact-directory",
            "sha256": records.tree_sha256(artifact_directory),
        }
    ]

    _write_request(tmp_path, "blocked-respond", depends_on=["unfinished"])
    with pytest.raises(ValueError, match="blocked by dependencies"):
        ux_respond({"request": "blocked-respond", "status": "accepted"}, tmp_path)
    needs_info = ux_respond(
        {
            "request": "blocked-respond",
            "status": "needs_info",
            "reason": "The dependency needs an approved interface decision.",
        },
        tmp_path,
    )
    assert needs_info["verdict"] == "pass"

    _write_request(tmp_path, "symlink-artifact")
    outside = tmp_path.parent / f"{tmp_path.name}-external"
    outside.write_text("outside\n", encoding="utf-8")
    (tmp_path / "artifact-link").symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"):
        ux_respond(
            {
                "request": "symlink-artifact",
                "status": "accepted",
                "artifacts": ["artifact-link"],
            },
            tmp_path,
        )
    assert not (tmp_path / "liaison" / "symlink-artifact.ux-response.json").exists()


@pytest.mark.parametrize("verdict", ["fail", "unknown"])
def test_done_response_requires_passing_gates_and_real_references(
    tmp_path: Path, verdict: str
) -> None:
    _write_request(tmp_path, "done-check")
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("release artifact\n", encoding="utf-8")
    base = {
        "request": "done-check",
        "status": "done",
        "reason": "Completed the production work and checked all requested evidence.",
        "artifacts": ["artifact.txt"],
    }
    with pytest.raises(ValueError, match="passing gates"):
        ux_respond(
            base | {"gate_verdicts": [{"gate": "prodeng-gates", "verdict": verdict}]},
            tmp_path,
        )
    passing = [{"gate": "prodeng-gates", "verdict": "pass"}]
    with pytest.raises(ValueError, match="decision_ref"):
        ux_respond(base | {"gate_verdicts": passing}, tmp_path)
    with pytest.raises(ValueError, match="do not exist"):
        ux_respond(
            base
            | {
                "gate_verdicts": passing,
                "decision_refs": ["a" * 64],
                "impression_refs": ["b" * 64],
            },
            tmp_path,
        )


def test_done_response_uses_real_records_and_contract_gates(tmp_path: Path) -> None:
    contract_path = _copy_example(tmp_path)
    input_path = contract_path.relative_to(tmp_path).as_posix()
    _write_request(tmp_path, "done-success", input_path=input_path)
    decision_id, impression_id = _write_real_records(tmp_path)

    result = ux_respond(
        {
            "request": "done-success",
            "status": "done",
            "reason": "Completed the production work and verified its gate evidence.",
            "artifacts": ["artifact.txt"],
            "contract_path": input_path,
            "decision_refs": [decision_id],
            "impression_refs": [impression_id],
        },
        tmp_path,
    )

    assert result["verdict"] == "pass"
    response = result["response"]
    assert isinstance(response, dict)
    assert response["status"] == "done"
    assert response["input_hashes"][input_path] == _input_hash(contract_path)
    assert response["artifacts"] == [
        {"path": "artifact.txt", "sha256": _input_hash(tmp_path / "artifact.txt")}
    ]
    assert response["gate_verdicts"]
    gate_verdicts = cast(list[dict[str, object]], response["gate_verdicts"])
    assert all(item["verdict"] == "pass" for item in gate_verdicts)


def test_respond_rejects_gate_disagreement_and_short_reasons(tmp_path: Path) -> None:
    contract_path = _copy_example(tmp_path)
    relative = contract_path.relative_to(tmp_path).as_posix()
    _write_request(tmp_path, "gate-disagreement", input_path=relative)
    with pytest.raises(ValueError, match="disagrees"):
        ux_respond(
            {
                "request": "gate-disagreement",
                "status": "accepted",
                "contract_path": relative,
                "gate_verdicts": [{"gate": "prodeng-gates", "verdict": "fail"}],
            },
            tmp_path,
        )
    with pytest.raises(ValidationError, match="20 characters"):
        ux_respond(
            {"request": "gate-disagreement", "status": "needs_info", "reason": "Need more."},
            tmp_path,
        )


def test_ux_inbox_respond_cli_and_mcp_entrypoints(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("OPENHANDS_PROJECT_DIR", str(tmp_path))
    _write_request(tmp_path, "cli-request")
    assert main(["ux", "inbox"]) == 0
    cli_inbox = json.loads(capsys.readouterr().out)
    assert cli_inbox["requests"][0]["id"] == "cli-request"

    input_json = tmp_path / "respond.json"
    input_json.write_text(
        json.dumps({"request": "cli-request", "status": "accepted"}),
        encoding="utf-8",
    )
    assert main(["ux", "respond", "--json", str(input_json)]) == 0
    assert json.loads(capsys.readouterr().out)["verdict"] == "pass"

    _write_request(tmp_path, "mcp-request")
    inbox_result = _call_tool("prodeng_ux_inbox", {})
    assert inbox_result.isError is False
    assert any(item["id"] == "mcp-request" for item in _tool_json(inbox_result)["requests"])
    respond_result = _call_tool(
        "prodeng_ux_respond",
        {"request": "mcp-request", "status": "accepted"},
    )
    assert respond_result.isError is False
    assert _tool_json(respond_result)["response"]["request"] == "mcp-request"

    tools = {tool.name: tool for tool in mcp_server.tool_specs()}
    assert tools["prodeng_ux_inbox"].annotations is not None
    assert tools["prodeng_ux_inbox"].annotations.readOnlyHint is True
    assert tools["prodeng_ux_respond"].annotations is not None
    assert tools["prodeng_ux_respond"].annotations.readOnlyHint is False
    assert tools["prodeng_ux_respond"].inputSchema == UxRespondInput.model_json_schema()
