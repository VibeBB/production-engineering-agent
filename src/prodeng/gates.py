"""Fail-closed production-engineering checks."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from .contract import ImportRef, Inspection, ProdengContract
from .sampling import SamplingPlan, sampling_plan

Verdict = Literal["pass", "fail", "unknown"]
GateStatus = Verdict


@dataclass(frozen=True)
class GateCheck:
    id: str
    subject: str
    status: GateStatus
    measured: int | float | str | None = None
    limit: int | float | str | None = None
    detail: str = ""


@dataclass(frozen=True)
class GateReport:
    checks: tuple[GateCheck, ...]
    verdict: Verdict

    def to_dict(self, contract: ProdengContract | None = None) -> dict[str, object]:
        result: dict[str, object] = {
            "verdict": self.verdict,
            "checks": [asdict(check) for check in self.checks],
        }
        if contract is not None:
            result["product"] = contract.product.name
            result["revision"] = contract.product.revision
        return result


def _check(
    check_id: str,
    subject: str,
    status: GateStatus,
    measured: int | float | str | None = None,
    limit: int | float | str | None = None,
    detail: str = "",
) -> GateCheck:
    return GateCheck(check_id, subject, status, measured, limit, detail)


def _inspection_sampling(inspection: Inspection, contract: ProdengContract) -> SamplingPlan | None:
    if inspection.sampling.mode == "full":
        return None
    if inspection.sampling.aql is None:
        return None
    return sampling_plan(
        contract.volume.lot_size,
        inspection.sampling.aql,
        inspection.sampling.level,
    )


def _gate_checks(contract: ProdengContract, contract_dir: Path) -> list[GateCheck]:
    checks: list[GateCheck] = []
    by_characteristic: dict[str, list[Inspection]] = {
        item.id: [] for item in contract.characteristics
    }
    for inspection in contract.inspections:
        by_characteristic[inspection.characteristic].append(inspection)

    for characteristic in sorted(contract.characteristics, key=lambda item: item.id):
        inspections = by_characteristic[characteristic.id]
        checks.append(
            _check(
                "coverage.characteristic",
                characteristic.id,
                "pass" if inspections else "fail",
                len(inspections),
                ">=1",
                "inspection coverage present" if inspections else "no linked inspection",
            )
        )
        if characteristic.classification == "critical":
            full = [inspection for inspection in inspections if inspection.sampling.mode == "full"]
            checks.append(
                _check(
                    "coverage.critical_full",
                    characteristic.id,
                    "pass" if full else "fail",
                    len(full),
                    ">=1",
                    "full inspection present" if full else "no full inspection",
                )
            )

    for inspection in sorted(contract.inspections, key=lambda item: item.id):
        if inspection.sampling.mode == "full":
            continue
        try:
            plan = _inspection_sampling(inspection, contract)
        except ValueError as exc:
            checks.append(
                _check(
                    "sampling.plan",
                    inspection.id,
                    "unknown",
                    detail=str(exc),
                )
            )
        else:
            if plan is None:
                checks.append(
                    _check(
                        "sampling.plan",
                        inspection.id,
                        "unknown",
                        detail="sampling plan is unavailable",
                    )
                )
            else:
                checks.append(
                    _check(
                        "sampling.plan",
                        inspection.id,
                        "pass",
                        plan.sample_size,
                        contract.volume.lot_size,
                        f"{plan.code_letter}, Ac {plan.accept}, Re {plan.reject}",
                    )
                )

    stations: dict[str, list[float | None]] = {}
    for operation in contract.operations:
        stations.setdefault(operation.station, []).append(operation.cycle_time_s)
    for station, times in sorted(stations.items()):
        missing = any(value is None for value in times)
        measured = None if missing else sum(value for value in times if value is not None)
        status: GateStatus = (
            "unknown"
            if missing
            else "pass"
            if measured is not None and measured <= contract.volume.takt_s
            else "fail"
        )
        checks.append(
            _check(
                "takt.station",
                station,
                status,
                measured,
                contract.volume.takt_s,
                "cycle time unavailable" if missing else "station total compared with takt",
            )
        )

    has_fct = any(inspection.method == "fct" for inspection in contract.inspections)
    if has_fct:
        checks.append(
            _check(
                "ftm.present",
                contract.product.name,
                "pass" if contract.factory_test_mode else "fail",
                "declared" if contract.factory_test_mode else "missing",
                "factory_test_mode required",
                "FCT inspection requires a declared factory-test mode",
            )
        )

    ftm = contract.factory_test_mode
    if ftm is not None:
        checks.append(
            _check(
                "ftm.entry_guard",
                contract.product.name,
                "pass" if len(ftm.entry.conditions) >= 2 else "fail",
                len(ftm.entry.conditions),
                ">=2",
                "entry conditions",
            )
        )
        checks.append(
            _check(
                "ftm.lockout",
                contract.product.name,
                "fail" if ftm.field_lockout.method == "none" else "pass",
                ftm.field_lockout.method,
                "not none",
                ftm.field_lockout.detail,
            )
        )
        duration = sum(command.timeout_ms for command in ftm.commands) / 1000
        checks.append(
            _check(
                "ftm.duration",
                contract.product.name,
                "pass" if duration <= ftm.max_duration_s else "fail",
                duration,
                ftm.max_duration_s,
                "sum of command timeouts",
            )
        )
        for command in sorted(ftm.commands, key=lambda item: item.id):
            used_by = [
                inspection.id
                for inspection in contract.inspections
                if command.id in inspection.ftm_commands
            ]
            valid = bool(command.covers) and bool(used_by)
            checks.append(
                _check(
                    "ftm.command_used",
                    command.id,
                    "pass" if valid else "fail",
                    f"covers={len(command.covers)}, inspections={len(used_by)}",
                    "covers >=1 CH and used >=1 IN",
                    "command coverage and inspection usage",
                )
            )
        for operation in sorted(contract.operations, key=lambda item: item.id):
            command_ids = {
                command_id
                for inspection in contract.inspections
                if inspection.operation == operation.id
                for command_id in inspection.ftm_commands
            }
            if not command_ids:
                continue
            timeout_s = sum(
                command.timeout_ms / 1000 for command in ftm.commands if command.id in command_ids
            )
            status = (
                "unknown"
                if operation.cycle_time_s is None
                else "pass"
                if timeout_s <= operation.cycle_time_s
                else "fail"
            )
            checks.append(
                _check(
                    "ftm.station_fit",
                    operation.id,
                    status,
                    timeout_s,
                    operation.cycle_time_s,
                    "timeout budget compared with operation cycle time",
                )
            )

    circuit_imports = [item for item in contract.imports if item.system == "circuit"]
    dft_nets = set(ftm.interface.nets if ftm else ())
    if ftm:
        dft_nets.update(net for command in ftm.commands for net in command.measures_nets)
    if not circuit_imports:
        checks.append(
            _check(
                "dft.test_access",
                "circuit import",
                "unknown",
                detail="no circuit import is available to verify test nets",
            )
        )
    else:
        available = {net for imported in circuit_imports for net in imported.extracted.nets}
        if not dft_nets:
            checks.append(
                _check(
                    "dft.test_access",
                    "declared test nets",
                    "pass",
                    0,
                    0,
                    "no interface or command measurement nets declared",
                )
            )
        for net in sorted(dft_nets):
            found = net in available
            checks.append(
                _check(
                    "dft.test_access",
                    net,
                    "pass" if found else "fail",
                    "present" if found else "missing",
                    "present in circuit import",
                    "circuit test access net",
                )
            )

    for failure_mode in sorted(contract.failure_modes, key=lambda item: item.id):
        controls = [
            inspection
            for inspection in contract.inspections
            if inspection.id in failure_mode.controls
        ]
        checks.append(
            _check(
                "pfmea.controls",
                failure_mode.id,
                "pass" if failure_mode.controls else "fail",
                len(failure_mode.controls),
                ">=1",
                "inspection control linked" if failure_mode.controls else "no controls",
            )
        )
        if failure_mode.severity >= 9:
            full = [inspection for inspection in controls if inspection.sampling.mode == "full"]
            checks.append(
                _check(
                    "pfmea.high_severity",
                    failure_mode.id,
                    "pass" if full else "fail",
                    len(full),
                    ">=1 full inspection control",
                    "high-severity risk control",
                )
            )

    hipot_operations = {
        inspection.operation
        for inspection in contract.inspections
        if inspection.method in ("hipot", "ground_bond")
    }
    for operation in sorted(contract.operations, key=lambda item: item.id):
        linked_safety_test = operation.id in hipot_operations
        safe = (not operation.safety_hazards or bool(operation.safety_precautions)) and (
            not linked_safety_test or bool(operation.safety_hazards)
        )
        checks.append(
            _check(
                "work_instruction.steps",
                operation.id,
                "pass"
                if operation.work_elements
                and all(element.key_points for element in operation.work_elements)
                else "fail",
                len(operation.work_elements),
                ">=1; every step has key points",
                "work-instruction step coverage",
            )
        )
        checks.append(
            _check(
                "work_instruction.safety",
                operation.id,
                "pass" if safe else "fail",
                f"hazards={len(operation.safety_hazards)}, "
                f"precautions={len(operation.safety_precautions)}",
                "hazard precautions; hazards for hipot/ground-bond",
                "safety instruction coverage",
            )
        )

    for imported in sorted(contract.imports, key=lambda item: (item.system, item.path)):
        checks.append(_freshness_check(imported, contract_dir))

    for question in sorted(
        (
            requirement
            for requirement in contract.requirements
            if requirement.id.startswith("Q") and requirement.status == "open"
        ),
        key=lambda item: item.id,
    ):
        checks.append(
            _check(
                "requirements.open_questions",
                question.id,
                "unknown",
                "open",
                "resolved",
                question.text,
            )
        )
    return checks


def _freshness_check(imported: ImportRef, contract_dir: Path) -> GateCheck:
    path = Path(imported.path)
    if not path.is_absolute():
        path = contract_dir / path
    if not path.is_file():
        return _check(
            "imports.fresh",
            imported.path,
            "unknown",
            detail="import file is missing",
        )
    try:
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        return _check(
            "imports.fresh",
            imported.path,
            "unknown",
            detail=f"could not read import file: {exc}",
        )
    matches = actual == imported.sha256
    return _check(
        "imports.fresh",
        imported.path,
        "pass" if matches else "fail",
        actual,
        imported.sha256,
        "sha256 matches" if matches else "sha256 mismatch",
    )


def run_gates(contract: ProdengContract, contract_dir: Path | str = ".") -> GateReport:
    checks = _gate_checks(contract, Path(contract_dir))
    verdict: Verdict = (
        "pass"
        if all(check.status == "pass" for check in checks)
        else "fail"
        if any(check.status == "fail" for check in checks)
        else "unknown"
    )
    return GateReport(tuple(checks), verdict)
