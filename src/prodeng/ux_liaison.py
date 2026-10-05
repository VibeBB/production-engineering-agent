"""Strict SLP v2 request validation and response writing."""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal, cast

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from .contract import load_contract
from .gates import run_gates
from .records import (
    LOG_FILES,
    DecisionRecord,
    StageImpression,
    VisionReview,
    sha256_file,
    tree_sha256,
)
from .workspace import reject_symlinks, workspace_path, workspace_root

type Slug = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$")]
type Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
type NonEmptyString = Annotated[str, Field(min_length=1)]

TargetAgent = Literal[
    "bard", "circuit", "dashboard", "doc", "firmware", "fpga", "mech", "prodeng", "sim", "wire"
]
Stage = Literal[
    "requirements", "design", "manufacturing_handoff", "build", "evaluation", "revision"
]
Risk = Literal["low", "high"]
ResponseStatus = Literal["accepted", "in_progress", "done", "rejected", "deferred", "needs_info"]
GateStatus = Literal["pass", "fail", "unknown"]
_JOB_CITATION = re.compile(
    r"\b(?:JOB-[A-Za-z0-9_-]+|job[-_:][A-Za-z0-9_-]+|"
    r"job\s+(?!(?:id|identifier|citation|reference|request|description|title|number)\b)"
    r"[a-z][a-z0-9_]*)\b",
    re.IGNORECASE,
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class UxInput(_StrictModel):
    path: NonEmptyString
    sha256: Sha256


class UxArtifact(_StrictModel):
    path: NonEmptyString
    sha256: Sha256


class GateVerdict(_StrictModel):
    gate: NonEmptyString
    verdict: GateStatus


class UxRequestV2(_StrictModel):
    schema_version: Literal[2]
    system: Literal["ux-creator"]
    id: Slug
    target_agent: TargetAgent
    stage: Stage
    risk: Risk
    purpose: str = Field(min_length=20)
    rationale: str
    requested_changes: list[NonEmptyString] = Field(min_length=1)
    inputs: list[UxInput] = Field(min_length=1)
    expected_deliverables: list[NonEmptyString] = Field(min_length=1)
    acceptance: list[NonEmptyString] = Field(min_length=1)
    depends_on: list[Slug] = Field(default_factory=list)
    created_at: AwareDatetime

    @model_validator(mode="after")
    def _high_risk_has_job_citation(self) -> UxRequestV2:
        if self.risk == "high" and _JOB_CITATION.search(self.rationale) is None:
            raise ValueError("high-risk requests must cite a UX job id in the rationale")
        return self


class UxResponseV2(_StrictModel):
    schema_version: Literal[2]
    system: Literal["ux-creator"]
    request: Slug
    responder: TargetAgent
    status: ResponseStatus
    reason: str = ""
    input_hashes: dict[str, Sha256]
    artifacts: list[UxArtifact] = Field(default_factory=list[UxArtifact])
    gate_verdicts: list[GateVerdict] = Field(default_factory=list[GateVerdict])
    decision_refs: list[Sha256] = Field(default_factory=list[Sha256])
    impression_refs: list[Sha256] = Field(default_factory=list[Sha256])
    questions_for_user: list[str] = Field(default_factory=list[str])
    responded_at: AwareDatetime

    @model_validator(mode="after")
    def _reason_is_substantive(self) -> UxResponseV2:
        _validate_reason(self.status, self.reason)
        return self


class UxRespondInput(_StrictModel):
    request: Slug
    status: ResponseStatus
    reason: str = ""
    artifacts: list[NonEmptyString] = Field(default_factory=list[NonEmptyString])
    gate_verdicts: list[GateVerdict] = Field(default_factory=list[GateVerdict])
    contract_path: str | None = None
    decision_refs: list[Sha256] = Field(default_factory=list[Sha256])
    impression_refs: list[Sha256] = Field(default_factory=list[Sha256])
    questions_for_user: list[str] = Field(default_factory=list[str])

    @model_validator(mode="after")
    def _reason_is_substantive(self) -> UxRespondInput:
        _validate_reason(self.status, self.reason)
        return self


def _validate_reason(status: ResponseStatus, reason: str) -> None:
    if status not in ("accepted", "in_progress") and len(reason.strip()) < 20:
        raise ValueError("reason must contain at least 20 characters for this status")


def _relative_label(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _malformed(path: Path, root: Path, error: Exception | str) -> dict[str, str]:
    return {"path": _relative_label(path, root), "error": str(error)}


def _liaison_directory(root: Path) -> Path:
    return workspace_path("liaison", root)


def _load_requests(
    directory: Path, root: Path
) -> tuple[dict[str, tuple[Path, UxRequestV2]], list[dict[str, str]]]:
    loaded: dict[str, tuple[Path, UxRequestV2]] = {}
    malformed: list[dict[str, str]] = []
    for path in sorted(directory.glob("*.ux-request.json")):
        try:
            safe_path = workspace_path(path, root)
            request = UxRequestV2.model_validate_json(safe_path.read_text(encoding="utf-8"))
            stem = path.name.removesuffix(".ux-request.json")
            if request.id != stem:
                raise ValueError(f"request id {request.id!r} does not match filename stem {stem!r}")
        except (OSError, ValueError) as exc:
            malformed.append(_malformed(path, root, exc))
            continue
        loaded[request.id] = (path, request)
    return loaded, malformed


def _load_responses(
    directory: Path, root: Path
) -> tuple[dict[str, tuple[Path, UxResponseV2]], list[dict[str, str]]]:
    loaded: dict[str, tuple[Path, UxResponseV2]] = {}
    malformed: list[dict[str, str]] = []
    for path in sorted(directory.glob("*.ux-response.json")):
        try:
            safe_path = workspace_path(path, root)
            response = UxResponseV2.model_validate_json(safe_path.read_text(encoding="utf-8"))
            stem = path.name.removesuffix(".ux-response.json")
            if response.request != stem:
                raise ValueError(
                    f"response request {response.request!r} does not match filename stem {stem!r}"
                )
        except (OSError, ValueError) as exc:
            malformed.append(_malformed(path, root, exc))
            continue
        loaded[response.request] = (path, response)
    return loaded, malformed


def _current_input_hashes(
    request: UxRequestV2,
    root: Path,
    *,
    missing_is_error: bool,
) -> tuple[dict[str, str], list[str]]:
    current: dict[str, str] = {}
    changes: list[str] = []
    for item in request.inputs:
        try:
            path = workspace_path(item.path, root)
            if not path.exists():
                if missing_is_error:
                    raise ValueError(f"request input is missing: {item.path}")
                changes.append(f"{item.path} (missing)")
                continue
            reject_symlinks(path)
            if not path.is_file() and not path.is_dir():
                raise ValueError(f"request input is not a file or directory: {item.path}")
            digest = tree_sha256(path)
        except (OSError, ValueError) as exc:
            if missing_is_error:
                raise ValueError(str(exc)) from exc
            changes.append(f"{item.path} ({exc})")
            continue
        current[item.path] = digest
        if digest != item.sha256:
            changes.append(f"{item.path} (sha256 changed)")
    return current, changes


def _validate_declared_job(request: UxRequestV2, root: Path) -> None:
    if request.risk != "high":
        return
    declared: set[str] = set()
    for item in request.inputs:
        try:
            path = workspace_path(item.path, root)
            if not path.is_file() or path.suffix.lower() != ".json":
                continue
            reject_symlinks(path)
            raw_data: object = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(raw_data, dict):
            continue
        data = cast(dict[str, object], raw_data)
        jobs = data.get("jobs")
        if isinstance(jobs, list):
            for raw_job in cast(list[object], jobs):
                if isinstance(raw_job, dict):
                    job = cast(dict[str, object], raw_job)
                    job_id = job.get("id")
                    if isinstance(job_id, str):
                        declared.add(job_id.lower())
    if declared:
        rationale_tokens = set(re.findall(r"\b[a-z][a-z0-9_-]*\b", request.rationale.lower()))
        if not (declared & rationale_tokens):
            raise ValueError("high-risk rationale does not cite a declared UX job id")


def _input_state(
    request: UxRequestV2, response: UxResponseV2 | None, root: Path
) -> tuple[bool, str]:
    current, changes = _current_input_hashes(request, root, missing_is_error=False)
    if changes:
        return True, "changed or unavailable inputs: " + "; ".join(changes)
    if (
        response is not None
        and response.responder == "prodeng"
        and response.input_hashes != current
    ):
        return True, "prodeng response input hashes differ from current inputs"
    return False, ""


def ux_inbox(root: Path | None = None) -> dict[str, object]:
    base = (root or workspace_root()).resolve()
    malformed: list[dict[str, str]] = []
    counts = {"new": 0, "stale": 0, "answered": 0, "blocked": 0}
    try:
        directory = _liaison_directory(base)
    except ValueError as exc:
        return {
            "verdict": "pass",
            "requests": [],
            "malformed": [_malformed(base / "liaison", base, exc)],
            "counts": counts,
        }
    if not directory.exists():
        return {"verdict": "pass", "requests": [], "malformed": [], "counts": counts}
    if not directory.is_dir():
        return {
            "verdict": "pass",
            "requests": [],
            "malformed": [_malformed(directory, base, "liaison path is not a directory")],
            "counts": counts,
        }

    requests, request_errors = _load_requests(directory, base)
    responses, response_errors = _load_responses(directory, base)
    malformed.extend(request_errors)
    malformed.extend(response_errors)
    result: list[dict[str, object]] = []
    for request_id, (_, request) in sorted(requests.items()):
        if request.target_agent != "prodeng":
            continue
        try:
            _validate_declared_job(request, base)
        except ValueError as exc:
            malformed.append(_malformed(directory / f"{request_id}.ux-request.json", base, exc))
            continue
        response_entry = responses.get(request_id)
        response = response_entry[1] if response_entry is not None else None
        stale, detail = _input_state(request, response, base)
        if stale:
            state = "stale"
        elif response is not None and response.responder == "prodeng":
            state = "answered"
            detail = "valid prodeng response exists"
        else:
            blocked = [
                dependency
                for dependency in request.depends_on
                if dependency not in responses or responses[dependency][1].status != "done"
            ]
            if blocked:
                state = "blocked"
                detail = "waiting for done responses: " + ", ".join(blocked)
            else:
                state = "new"
                detail = ""
        counts[state] += 1
        result.append(
            {
                "id": request.id,
                "stage": request.stage,
                "risk": request.risk,
                "purpose": request.purpose,
                "depends_on": request.depends_on,
                "state": state,
                "detail": detail,
            }
        )
    malformed.sort(key=lambda item: item["path"])
    return {"verdict": "pass", "requests": result, "malformed": malformed, "counts": counts}


def _record_event_ids(filename: str, model: type[BaseModel], root: Path) -> set[str]:
    path = workspace_path(Path("observations") / "prodeng" / filename, root)
    if not path.exists():
        return set()
    reject_symlinks(path)
    event_ids: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = model.model_validate_json(line)
        except ValueError:
            continue
        event_id = getattr(record, "event_id", None)
        if isinstance(event_id, str):
            event_ids.add(event_id)
    return event_ids


def _artifact_ref(value: str, root: Path) -> UxArtifact:
    path = workspace_path(value, root)
    if not path.exists():
        raise ValueError(f"artifact does not exist: {value}")
    reject_symlinks(path)
    if not path.is_file() and not path.is_dir():
        raise ValueError(f"artifact is not a file or directory: {value}")
    relative = path.relative_to(root).as_posix()
    digest = sha256_file(path) if path.is_file() else tree_sha256(path)
    return UxArtifact(path=relative, sha256=digest)


def _check_dependencies(
    request: UxRequestV2,
    response_status: ResponseStatus,
    responses: dict[str, tuple[Path, UxResponseV2]],
) -> None:
    blocked = [
        dependency
        for dependency in request.depends_on
        if dependency not in responses or responses[dependency][1].status != "done"
    ]
    if blocked and response_status not in ("needs_info", "deferred", "rejected"):
        raise ValueError(
            "request is blocked by dependencies without valid done responses: " + ", ".join(blocked)
        )


def _gate_verdicts(payload: UxRespondInput, root: Path) -> list[GateVerdict]:
    verdicts = list(payload.gate_verdicts)
    if payload.contract_path is None:
        return verdicts
    path = workspace_path(payload.contract_path, root)
    if not path.is_file():
        raise ValueError(f"contract does not exist: {payload.contract_path}")
    reject_symlinks(path)
    report = run_gates(load_contract(path), path.parent)
    computed = [GateVerdict(gate=check.id, verdict=check.status) for check in report.checks]
    computed.append(GateVerdict(gate="prodeng-gates", verdict=report.verdict))
    by_gate: dict[str, set[str]] = {}
    for item in computed:
        by_gate.setdefault(item.gate, set()).add(item.verdict)
    for supplied in payload.gate_verdicts:
        expected = by_gate.get(supplied.gate)
        if expected is not None and (len(expected) != 1 or supplied.verdict not in expected):
            raise ValueError(
                f"caller gate verdict for {supplied.gate!r} disagrees with computed gates"
            )
    for item in computed:
        if item not in verdicts:
            verdicts.append(item)
    return verdicts


def _validated_request(request_id: str, root: Path) -> UxRequestV2:
    directory = _liaison_directory(root)
    path = workspace_path(directory / f"{request_id}.ux-request.json", root)
    if not path.is_file():
        raise ValueError(f"UX request does not exist: {request_id}")
    request = UxRequestV2.model_validate_json(path.read_text(encoding="utf-8"))
    if request.id != request_id:
        raise ValueError(f"request id {request.id!r} does not match filename stem {request_id!r}")
    if request.target_agent != "prodeng":
        raise ValueError(f"UX request {request_id!r} targets {request.target_agent!r}, not prodeng")
    _validate_declared_job(request, root)
    return request


def ux_respond(payload: Mapping[str, object], root: Path | None = None) -> dict[str, object]:
    base = (root or workspace_root()).resolve()
    response_input = UxRespondInput.model_validate(dict(payload))
    request = _validated_request(response_input.request, base)
    directory = _liaison_directory(base)
    if directory.exists() and not directory.is_dir():
        raise ValueError("liaison path is not a directory")
    directory.mkdir(parents=True, exist_ok=True)
    directory = workspace_path("liaison", base)
    reject_symlinks(directory)
    responses, _ = _load_responses(directory, base)
    _check_dependencies(request, response_input.status, responses)

    input_hashes, _ = _current_input_hashes(request, base, missing_is_error=True)
    artifacts = [_artifact_ref(value, base) for value in response_input.artifacts]
    gate_verdicts = _gate_verdicts(response_input, base)
    decision_ids = _record_event_ids(LOG_FILES["decision"], DecisionRecord, base)
    impression_ids = _record_event_ids(
        LOG_FILES["stage_impression"], StageImpression, base
    ) | _record_event_ids(LOG_FILES["vision_review"], VisionReview, base)
    unknown_decisions = sorted(set(response_input.decision_refs) - decision_ids)
    unknown_impressions = sorted(set(response_input.impression_refs) - impression_ids)
    if unknown_decisions:
        raise ValueError(
            f"decision_refs do not exist in prodeng decision records: {unknown_decisions}"
        )
    if unknown_impressions:
        raise ValueError(
            "impression_refs do not exist in prodeng impression or vision records: "
            f"{unknown_impressions}"
        )
    if response_input.status == "done":
        if not artifacts:
            raise ValueError("done responses require at least one artifact")
        if not gate_verdicts or any(item.verdict != "pass" for item in gate_verdicts):
            raise ValueError(
                "done responses require passing gates; answer needs_info or rejected with a reason"
            )
        if not response_input.decision_refs:
            raise ValueError("done responses require at least one decision_ref")
        if not response_input.impression_refs:
            raise ValueError("done responses require at least one impression_ref")

    response = UxResponseV2(
        schema_version=2,
        system="ux-creator",
        request=request.id,
        responder="prodeng",
        status=response_input.status,
        reason=response_input.reason,
        input_hashes=input_hashes,
        artifacts=artifacts,
        gate_verdicts=gate_verdicts,
        decision_refs=response_input.decision_refs,
        impression_refs=response_input.impression_refs,
        questions_for_user=response_input.questions_for_user,
        responded_at=datetime.now(UTC),
    )
    response_path = workspace_path(
        directory / f"{request.id}.ux-response.json",
        base,
    )
    temp_path: Path | None = None
    try:
        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{request.id}.", suffix=".tmp", dir=directory
        )
        temp_path = Path(temp_name)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(response.model_dump(mode="json"), indent=2, sort_keys=True))
            stream.write("\n")
        os.replace(temp_path, response_path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
    return {
        "verdict": "pass",
        "path": response_path.relative_to(base).as_posix(),
        "response": response.model_dump(mode="json"),
    }
