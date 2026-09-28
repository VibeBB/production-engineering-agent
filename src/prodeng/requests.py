"""Deterministic sibling change requests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contract import ProdengContract
from .gates import GateReport

TARGET_AGENTS = ("circuit", "firmware", "mech", "wire", "ux", "document", "bard")


class ProdengRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    system: Literal["prodeng"] = "prodeng"
    target_agent: Literal["circuit", "firmware", "mech", "wire", "ux", "document", "bard"]
    topic: str = Field(min_length=1)
    risk: Literal["low", "high"]
    rationale: str = Field(min_length=1)
    cites: list[str] = Field(default_factory=list)
    requested_changes: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def high_risk_has_cite(self) -> ProdengRequest:
        if self.risk == "high" and not self.cites:
            raise ValueError("high-risk requests must cite at least one declared CH/R/IN id")
        return self


def _declared_cites(contract: ProdengContract) -> set[str]:
    return (
        {item.id for item in contract.characteristics}
        | {item.id for item in contract.requirements}
        | {item.id for item in contract.inspections}
    )


def build_request(
    contract: ProdengContract,
    *,
    target_agent: str,
    topic: str,
    risk: Literal["low", "high"],
    rationale: str,
    cites: list[str],
    requested_changes: list[str],
) -> ProdengRequest:
    if target_agent not in TARGET_AGENTS:
        raise ValueError(f"unknown target_agent {target_agent!r}; expected one of {TARGET_AGENTS}")
    declared = _declared_cites(contract)
    if risk == "high" and not (set(cites) & declared):
        raise ValueError(
            "high-risk requests must cite at least one declared CH/R/IN id "
            f"(declared: {sorted(declared)})"
        )
    if any(cite not in declared for cite in cites):
        raise ValueError(f"request cites undeclared ids: {sorted(set(cites) - declared)}")
    return ProdengRequest(
        target_agent=target_agent,
        topic=topic,
        risk=risk,
        rationale=rationale,
        cites=sorted(set(cites)),
        requested_changes=requested_changes,
    )


def _high_risk_cites(contract: ProdengContract, preferred: set[str]) -> list[str]:
    declared = _declared_cites(contract)
    selected = sorted(preferred & declared)
    if not selected:
        selected = sorted(declared)[:1]
    return selected


def derive_requests(contract: ProdengContract, gate_report: GateReport) -> list[ProdengRequest]:
    derived: list[ProdengRequest] = []
    ftm = contract.factory_test_mode
    if ftm is not None:
        cited = {characteristic for command in ftm.commands for characteristic in command.covers}
        cited.update(
            inspection.id for inspection in contract.inspections if inspection.method == "fct"
        )
        command_lines = [
            f"{command.id}: {command.request} -> {command.response_pattern} "
            f"(timeout {command.timeout_ms} ms)"
            for command in sorted(ftm.commands, key=lambda item: item.id)
        ]
        derived.append(
            build_request(
                contract,
                target_agent="firmware",
                topic="factory-test-mode",
                risk="high",
                rationale=(
                    "Implement the guarded factory test mode, field lockout, "
                    "and bounded command protocol."
                ),
                cites=_high_risk_cites(contract, cited),
                requested_changes=[
                    f"Entry: {ftm.entry.method}; {ftm.entry.detail}; "
                    f"conditions: {'; '.join(ftm.entry.conditions)}.",
                    f"Field lockout: {ftm.field_lockout.method}; {ftm.field_lockout.detail}.",
                    f"Interface: {ftm.interface.transport}; {ftm.interface.settings}; "
                    f"nets: {', '.join(sorted(ftm.interface.nets)) or 'none'}.",
                    *command_lines,
                    *[
                        f"Provision {item.item} from {item.source}; "
                        f"write_once={str(item.write_once).lower()}."
                        for item in ftm.provisioning
                    ],
                    f"Exit: {ftm.exit}.",
                    f"Total command timeout budget: "
                    f"{sum(item.timeout_ms for item in ftm.commands) / 1000:g} s; "
                    f"maximum: {ftm.max_duration_s:g} s.",
                ],
            )
        )

    failing_access = any(
        check.id == "dft.test_access" and check.status == "fail" for check in gate_report.checks
    )
    ftm_nets = bool(
        ftm and (ftm.interface.nets or any(command.measures_nets for command in ftm.commands))
    )
    strap_entry = bool(ftm and ftm.entry.method == "gpio_strap")
    if ftm_nets or failing_access or strap_entry:
        cites = {inspection.id for inspection in contract.inspections if inspection.method == "fct"}
        if ftm is not None:
            cites.update(command.covers[0] for command in ftm.commands if command.covers)
        nets = sorted(
            set(ftm.interface.nets if ftm else ())
            | {net for command in ftm.commands for net in command.measures_nets}
            if ftm
            else set()
        )
        derived.append(
            build_request(
                contract,
                target_agent="circuit",
                topic="test-access",
                risk="high",
                rationale=(
                    "Provide physical and electrical access for guarded factory "
                    "test and measurements."
                ),
                cites=_high_risk_cites(contract, cites),
                requested_changes=[
                    "Provide test access for nets: "
                    + (", ".join(nets) if nets else "review failing access checks"),
                    (
                        "Review the GPIO strap entry path and expose test points "
                        "or connector access where required."
                        if strap_entry
                        else "Resolve circuit-side factory-test access gaps."
                    ),
                ],
            )
        )

    fixture_ops = [operation for operation in contract.operations if operation.fixtures]
    if fixture_ops:
        derived.append(
            build_request(
                contract,
                target_agent="mech",
                topic="fixtures",
                risk="low",
                rationale="Coordinate operation-specific assembly and inspection fixtures.",
                cites=[],
                requested_changes=[
                    f"{operation.id} ({operation.name}, station {operation.station}): "
                    f"provide or verify fixture(s) {', '.join(sorted(operation.fixtures))}."
                    for operation in sorted(fixture_ops, key=lambda item: item.id)
                ],
            )
        )

    harness_ops = [operation for operation in contract.operations if operation.kind == "harness"]
    if harness_ops:
        derived.append(
            build_request(
                contract,
                target_agent="wire",
                topic="harness-test",
                risk="low",
                rationale=(
                    "Align harness manufacture with production continuity and safety inspection."
                ),
                cites=[],
                requested_changes=[
                    (
                        "Provide a harness continuity test table with connector "
                        "pin, net, and pass criteria."
                    ),
                    (
                        "Coordinate hipot and ground-bond testability and reaction "
                        "criteria where applicable."
                    ),
                    *[
                        f"Support {operation.id} ({operation.name}) at {operation.station}."
                        for operation in sorted(harness_ops, key=lambda item: item.id)
                    ],
                ],
            )
        )

    derived.append(
        build_request(
            contract,
            target_agent="document",
            topic="work-instructions",
            risk="low",
            rationale=(
                "Typeset and control the manufacturing work instructions and QC control plan."
            ),
            cites=[],
            requested_changes=[
                (
                    "Create controlled work instructions from the operation TWI "
                    "major-step, key-point, and reason tables."
                ),
                "Typeset the inspection/control plan with reaction plans and sampling criteria.",
            ],
        )
    )
    return derived


def write_request(request: ProdengRequest, out_dir: Path, name: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.prodeng-request.json"
    path.write_text(
        json.dumps(request.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def write_requests(contract: ProdengContract, gate_report: GateReport, out_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for request in derive_requests(contract, gate_report):
        stem = f"{contract.product.name}-{request.target_agent}-{request.topic}"
        paths.append(write_request(request, out_dir, stem))
    return paths
