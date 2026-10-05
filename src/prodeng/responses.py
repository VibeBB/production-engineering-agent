"""Reconcile sibling responses to production-engineering requests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from .requests import TARGET_AGENTS, ProdengRequest, TargetAgent

ResponseStatus = Literal["accepted", "rejected", "deferred", "needs_info"]
type Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class ResponseArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1)
    sha256: Sha256


class ProdengResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[2] = 2
    system: Literal["prodeng"] = "prodeng"
    request: str = Field(min_length=1)
    responder: TargetAgent
    status: ResponseStatus
    reason: str = ""
    artifacts: list[ResponseArtifact] = Field(default_factory=list[ResponseArtifact])
    input_hashes: dict[str, Sha256]
    decision_refs: list[Sha256] = Field(default_factory=list)


class LiaisonEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request: str
    target_agent: str
    risk: Literal["low", "high"]
    state: Literal["open", "answered", "mismatched", "stale"]
    response_status: ResponseStatus | None = None
    reason: str = ""
    response_path: str = ""


class LiaisonStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    entries: list[LiaisonEntry]
    orphans: list[str]
    malformed: list[str]


def _normalise_request_ref(reference: str) -> str:
    for suffix in (".prodeng-request.json", ".json"):
        if reference.endswith(suffix):
            return reference.removesuffix(suffix)
    return reference


def _load_requests(directory: Path) -> tuple[list[tuple[Path, ProdengRequest]], list[Path]]:
    valid: list[tuple[Path, ProdengRequest]] = []
    malformed: list[Path] = []
    for path in sorted(directory.glob("*.prodeng-request.json")):
        try:
            request = ProdengRequest.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            malformed.append(path)
            continue
        valid.append((path, request))
    return valid, malformed


def _load_responses(directory: Path) -> tuple[list[tuple[Path, ProdengResponse]], list[Path]]:
    valid: list[tuple[Path, ProdengResponse]] = []
    malformed: list[Path] = []
    for path in sorted(directory.glob("*.prodeng-response.json")):
        try:
            response = ProdengResponse.model_validate(json.loads(path.read_text(encoding="utf-8")))
            if response.responder not in TARGET_AGENTS:
                raise ValueError(f"unknown responder {response.responder!r}")
        except (OSError, ValueError):
            malformed.append(path)
            continue
        valid.append((path, response))
    return valid, malformed


def liaison_status(requests_dir: Path, responses_dir: Path | None = None) -> LiaisonStatus:
    response_directory = responses_dir or requests_dir
    requests, malformed_requests = _load_requests(requests_dir)
    responses, malformed_responses = _load_responses(response_directory)
    latest: dict[str, tuple[Path, ProdengResponse]] = {}
    for path, response in responses:
        latest[_normalise_request_ref(response.request)] = (path, response)
    entries: list[LiaisonEntry] = []
    seen: set[str] = set()
    for path, request in requests:
        stem = path.name.removesuffix(".prodeng-request.json")
        seen.add(stem)
        response_entry = latest.get(stem)
        if response_entry is None:
            entries.append(
                LiaisonEntry(
                    request=stem,
                    target_agent=request.target_agent,
                    risk=request.risk,
                    state="open",
                )
            )
            continue
        response_path, response = response_entry
        request_hashes = {item.path: item.sha256 for item in request.inputs}
        if response.input_hashes != request_hashes:
            state = "stale"
        else:
            state = "answered" if response.responder == request.target_agent else "mismatched"
        entries.append(
            LiaisonEntry(
                request=stem,
                target_agent=request.target_agent,
                risk=request.risk,
                state=state,
                response_status=response.status,
                reason=response.reason,
                response_path=str(response_path),
            )
        )
    orphans = sorted(str(path) for stem, (path, _) in latest.items() if stem not in seen)
    entries.sort(key=lambda entry: entry.request)
    return LiaisonStatus(
        entries=entries,
        orphans=orphans,
        malformed=sorted(str(path) for path in malformed_requests + malformed_responses),
    )
