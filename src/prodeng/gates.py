"""Fail-closed production-engineering checks."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, cast

from pydantic import ValidationError

from .contract import Characteristic, ImportRef, Inspection, ProdengContract
from .imports import FirmwareProductionSource, FpgaProductionSource
from .projections import ftm_spec_bytes
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
        if imported.kind == "fpga-production":
            checks.append(_fpga_programming_check(contract, imported, contract_dir))
        if imported.kind == "firmware-production":
            checks.append(_firmware_programming_check(contract, imported, contract_dir))

    for characteristic in sorted(contract.characteristics, key=lambda item: item.id):
        if characteristic.simulation is not None:
            checks.append(_sim_prediction_check(characteristic, contract_dir))

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


def _fpga_programming_check(
    contract: ProdengContract, imported: ImportRef, contract_dir: Path
) -> GateCheck:
    """The programming operation loads exactly the bitstream fpga-agent gated."""
    gate = "fpga.programming"
    path = Path(imported.path)
    if not path.is_absolute():
        path = contract_dir / path
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return _check(gate, imported.path, "unknown", detail=f"artifact unreadable: {exc}")
    if hashlib.sha256(raw).hexdigest() != imported.sha256:
        return _check(gate, imported.path, "fail", detail="artifact changed since import")
    try:
        artifact = FpgaProductionSource.model_validate_json(raw)
    except ValidationError as exc:
        return _check(gate, imported.path, "fail", detail=f"malformed artifact: {exc}")
    subject = artifact.device_ref
    operations = sorted(op.id for op in contract.operations if subject in op.programs)
    if not operations:
        return _check(gate, subject, "fail", detail="no programming operation programs it")
    if artifact.target != "flash":
        return _check(
            gate,
            subject,
            "fail",
            artifact.target,
            "flash",
            "SRAM configuration is lost at power-off; set programmer.write_flash",
        )
    bitstream = path.parent / artifact.bitstream
    try:
        data = bitstream.read_bytes()
    except OSError as exc:
        return _check(gate, subject, "unknown", detail=f"bitstream unreadable: {exc}")
    digest = hashlib.sha256(data).hexdigest()
    if digest != artifact.bitstream_sha256 or len(data) != artifact.bitstream_bytes:
        return _check(
            gate,
            subject,
            "fail",
            digest,
            artifact.bitstream_sha256,
            "bitstream differs from the one fpga-agent gated",
        )
    return _check(
        gate,
        subject,
        "pass",
        digest,
        artifact.bitstream_sha256,
        f"{', '.join(operations)} runs: {' '.join(artifact.argv)}",
    )


def _ftm_problem(contract: ProdengContract, artifact: FirmwareProductionSource) -> str | None:
    ftm = contract.factory_test_mode
    if ftm is None:
        if artifact.ftm_spec_sha256 is not None:
            return "firmware serves a factory test spec this contract no longer declares"
        return None
    current = hashlib.sha256(ftm_spec_bytes(contract)).hexdigest()
    if artifact.ftm_spec_sha256 is None:
        return "firmware was gated without the factory test spec; pin it in the firmware ftm block"
    if artifact.ftm_spec_sha256 != current:
        return (
            f"firmware was gated against factory test spec {artifact.ftm_spec_sha256}, "
            f"current is {current}; re-pin ftm.sha256 in firmware and re-gate"
        )
    expected = sorted(command.id for command in ftm.commands)
    if artifact.ftm_commands != expected:
        return f"firmware serves {artifact.ftm_commands}, the spec declares {expected}"
    return None


def _firmware_programming_check(
    contract: ProdengContract, imported: ImportRef, contract_dir: Path
) -> GateCheck:
    """The programming operation flashes exactly the ELF firmware-agent gated."""
    gate = "firmware.programming"
    path = Path(imported.path)
    if not path.is_absolute():
        path = contract_dir / path
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return _check(gate, imported.path, "unknown", detail=f"artifact unreadable: {exc}")
    if hashlib.sha256(raw).hexdigest() != imported.sha256:
        return _check(gate, imported.path, "fail", detail="artifact changed since import")
    try:
        artifact = FirmwareProductionSource.model_validate_json(raw)
    except ValidationError as exc:
        return _check(gate, imported.path, "fail", detail=f"malformed artifact: {exc}")
    subject = artifact.mcu_ref
    operations = sorted(op.id for op in contract.operations if subject in op.programs)
    if not operations:
        return _check(gate, subject, "fail", detail="no programming operation programs it")
    elf = path.parent / artifact.elf
    try:
        data = elf.read_bytes()
    except OSError as exc:
        return _check(gate, subject, "unknown", detail=f"ELF unreadable: {exc}")
    digest = hashlib.sha256(data).hexdigest()
    if digest != artifact.elf_sha256 or len(data) != artifact.elf_bytes:
        return _check(
            gate,
            subject,
            "fail",
            digest,
            artifact.elf_sha256,
            "ELF differs from the one firmware-agent gated",
        )
    problem = _ftm_problem(contract, artifact)
    if problem is not None:
        return _check(gate, subject, "fail", digest, artifact.elf_sha256, problem)
    ftm = (
        f"serves {', '.join(artifact.ftm_commands)} of factory test spec {artifact.ftm_spec_sha256}"
        if artifact.ftm_spec_sha256
        else "no factory test mode"
    )
    return _check(
        gate,
        subject,
        "pass",
        digest,
        artifact.elf_sha256,
        f"{', '.join(operations)} flashes {artifact.elf} on {artifact.part} "
        f"({artifact.package}); {ftm}",
    )


def _window(characteristic: Characteristic) -> str:
    low = "-inf" if characteristic.lsl is None else f"{characteristic.lsl:g}"
    high = "+inf" if characteristic.usl is None else f"{characteristic.usl:g}"
    return f"[{low}, {high}] {characteristic.unit}"


def _sim_prediction_check(characteristic: Characteristic, contract_dir: Path) -> GateCheck:
    """Simulation must pass and predict the characteristic inside its production window."""
    prediction = characteristic.simulation
    assert prediction is not None
    window = _window(characteristic)

    def result(
        status: GateStatus, detail: str, measured: int | float | str | None = None
    ) -> GateCheck:
        return _check("sim.prediction", characteristic.id, status, measured, window, detail)

    path = Path(prediction.report_path)
    if not path.is_absolute():
        path = contract_dir / path
    if not path.is_file():
        return result("unknown", f"sim report is missing: {prediction.report_path}")
    try:
        data = path.read_bytes()
    except OSError as exc:
        return result("unknown", f"could not read sim report: {exc}")
    if hashlib.sha256(data).hexdigest() != prediction.sha256:
        return result("fail", "sim report changed since it was pinned (sha256 mismatch)")
    try:
        report: object = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return result("unknown", f"sim report is not JSON: {exc}")
    rows: list[object] = []
    if isinstance(report, dict):
        raw = cast(dict[str, object], report).get("checks")
        if isinstance(raw, list):
            rows = cast(list[object], raw)
    matches = [
        cast(dict[str, object], item)
        for item in rows
        if isinstance(item, dict) and cast(dict[str, object], item).get("id") == prediction.check_id
    ]
    if len(matches) != 1:
        return result("unknown", f"sim report has no single check {prediction.check_id}")
    row = matches[0]
    verdict = row.get("verdict")
    if verdict == "fail":
        return result("fail", f"simulation fails {prediction.check_id}")
    if verdict != "pass":
        return result("unknown", f"simulation verdict for {prediction.check_id} is {verdict!r}")
    measured = row.get("measured")
    if (
        isinstance(measured, bool)
        or not isinstance(measured, int | float)
        or not math.isfinite(measured)
    ):
        return result("unknown", f"{prediction.check_id} has no finite predicted value")
    low, high = characteristic.lsl, characteristic.usl
    if (low is not None and measured < low) or (high is not None and measured > high):
        return result(
            "fail", f"design predicts {measured:g} outside the production window", measured
        )
    headroom = min(
        measured - low if low is not None else math.inf,
        high - measured if high is not None else math.inf,
    )
    detail = f"predicted {measured:g} inside the window; headroom {headroom:g}"
    if low is not None and high is not None and high > low:
        detail += f" ({headroom / (high - low):.0%} of tolerance)"
    return result("pass", detail, measured)


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
