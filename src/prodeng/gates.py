"""Fail-closed production-engineering checks."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from itertools import pairwise
from pathlib import Path
from typing import Literal, cast

from pydantic import ValidationError

from .contract import CRIMP_UNITS, Characteristic, ImportRef, Inspection, ProdengContract
from .ebom import product_ebom
from .imports import (
    CircuitAssemblySource,
    CircuitHandlingSource,
    CrimpConditionMirror,
    FirmwareProductionSource,
    FpgaProductionSource,
    MechAppearanceSource,
    WireContinuitySource,
    WireCrimpSource,
    WireFormboardSource,
    mech_envelope_mm,
)
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
        if imported.kind == "mech-appearance":
            checks.extend(_appearance_checks(contract, imported, contract_dir))
        if imported.kind == "circuit-assembly":
            checks.extend(_assembly_checks(contract, imported, contract_dir))
        if imported.kind == "circuit-handling":
            checks.extend(_handling_checks(contract, imported, contract_dir))
        if imported.kind == "wire-crimp":
            checks.extend(_crimp_checks(contract, imported, contract_dir))
        if imported.kind == "wire-formboard":
            checks.append(_formboard_check(contract, imported, contract_dir))
        if imported.kind == "wire-continuity":
            checks.append(_continuity_check(contract, imported, contract_dir))

    if contract.packaging is not None:
        checks.extend(_packaging_checks(contract, contract_dir))
    if contract.ebom_sources:
        checks.append(_ebom_check(contract, contract_dir))

    for characteristic in sorted(contract.characteristics, key=lambda item: item.id):
        if characteristic.simulation is not None:
            checks.append(_sim_prediction_check(characteristic, contract_dir))
    checks.extend(_msa_checks(contract))

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


_ASSEMBLY_OPERATIONS: dict[str, tuple[str, ...]] = {
    "smd": ("smt",),
    "tht": ("tht", "selective_solder"),
}


def _assembly_checks(
    contract: ProdengContract, imported: ImportRef, contract_dir: Path
) -> list[GateCheck]:
    """Every populated mount/side group of the circuit board has an operation that places it."""
    gate = "circuit.assembly"
    path = Path(imported.path)
    if not path.is_absolute():
        path = contract_dir / path
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return [_check(gate, imported.path, "unknown", detail=f"artifact unreadable: {exc}")]
    if hashlib.sha256(raw).hexdigest() != imported.sha256:
        return [_check(gate, imported.path, "fail", detail="artifact changed since import")]
    try:
        board = CircuitAssemblySource.model_validate_json(raw)
    except ValidationError as exc:
        return [_check(gate, imported.path, "fail", detail=f"malformed artifact: {exc}")]
    if board.verdict != "pass":
        return [
            _check(
                gate,
                imported.path,
                "unknown",
                detail=f"circuit export is incomplete: {', '.join(board.unknown)}",
            )
        ]
    groups: dict[tuple[str, str], list[str]] = {}
    for item in board.populated():
        if item.mount is not None:
            groups.setdefault((item.mount, item.side), []).append(item.ref)
    if not groups:
        return [_check(gate, imported.path, "unknown", detail="no populated placements")]
    checks: list[GateCheck] = []
    placed = {item.ref for item in board.placements}
    for brief in contract.imports:
        if brief.kind == "circuit-brief":
            missing = sorted(set(brief.extracted.parts) - placed)
            checks.append(
                _check(
                    gate,
                    f"brief:{brief.path}",
                    "fail" if missing else "pass",
                    len(missing),
                    0,
                    f"board does not place {', '.join(missing)}"
                    if missing
                    else "board places every brief part",
                )
            )
    for (mount, side), refs in sorted(groups.items()):
        kinds = _ASSEMBLY_OPERATIONS[mount]
        operations = sorted(
            op.id for op in contract.operations if op.kind in kinds and side in op.sides
        )
        checks.append(
            _check(
                gate,
                f"{mount}:{side}",
                "pass" if operations else "fail",
                len(refs),
                f"{'/'.join(kinds)} operation with sides [{side!r}]",
                f"{', '.join(operations)} places {', '.join(sorted(refs))}"
                if operations
                else f"no operation places {', '.join(sorted(refs))}",
            )
        )
    return checks


_BOARD_OPERATIONS = ("smt", "tht", "selective_solder")


def _handling_checks(
    contract: ProdengContract, imported: ImportRef, contract_dir: Path
) -> list[GateCheck]:
    """ESD control, reflow peak and MSL floor-life control cover the circuit part facts."""
    gate = "circuit.handling"
    path = Path(imported.path)
    if not path.is_absolute():
        path = contract_dir / path
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return [_check(gate, imported.path, "unknown", detail=f"artifact unreadable: {exc}")]
    if hashlib.sha256(raw).hexdigest() != imported.sha256:
        return [_check(gate, imported.path, "fail", detail="artifact changed since import")]
    try:
        handling = CircuitHandlingSource.model_validate_json(raw)
    except ValidationError as exc:
        return [_check(gate, imported.path, "fail", detail=f"malformed artifact: {exc}")]
    if handling.verdict != "pass":
        return [
            _check(
                gate,
                imported.path,
                "unknown",
                detail=f"circuit parts lack handling facts: {', '.join(handling.unknown)}",
            )
        ]
    if not handling.parts:
        return [_check(gate, imported.path, "unknown", detail="no handled parts")]
    board_ops = [op for op in contract.operations if op.kind in _BOARD_OPERATIONS]
    smt_ops = [op for op in board_ops if op.kind == "smt"]
    checks: list[GateCheck] = []
    esd = sorted(item.ref for item in handling.parts if item.esd_sensitive)
    if esd:
        open_ops = sorted(op.id for op in board_ops if not op.esd_sensitive)
        checks.append(
            _check(
                gate,
                "esd",
                "fail" if open_ops or not board_ops else "pass",
                len(open_ops),
                0,
                f"{', '.join(open_ops)} handle {', '.join(esd)} without ESD control"
                if open_ops
                else "no board operation handles the ESD-sensitive parts"
                if not board_ops
                else f"ESD control covers {', '.join(esd)}",
            )
        )
    # Every part on the board rides through each reflow pass, so the coolest
    # part rating bounds every smt operation.
    coolest = min(handling.parts, key=lambda item: (item.peak_reflow_c, item.ref))
    for op in smt_ops:
        peak = op.reflow_peak_c
        checks.append(
            _check(
                gate,
                f"reflow:{op.id}",
                "unknown" if peak is None else "pass" if peak <= coolest.peak_reflow_c else "fail",
                peak,
                coolest.peak_reflow_c,
                f"{op.id} states no reflow_peak_c"
                if peak is None
                else f"{coolest.ref} is rated {coolest.peak_reflow_c:g} °C",
            )
        )
    sensitive = sorted(item.ref for item in handling.parts if item.msl != "1")
    if sensitive:
        uncontrolled = sorted(op.id for op in smt_ops if not op.floor_life_control)
        checks.append(
            _check(
                gate,
                "msl",
                "fail" if uncontrolled or not smt_ops else "pass",
                len(uncontrolled),
                0,
                f"{', '.join(uncontrolled)} reflow {', '.join(sensitive)} without "
                "floor_life_control"
                if uncontrolled
                else "no smt operation reflows the moisture-sensitive parts"
                if not smt_ops
                else f"floor-life control covers {', '.join(sensitive)}",
            )
        )
    return checks


def _crimp_limit_problem(
    characteristic: Characteristic, condition: CrimpConditionMirror, quantity: str
) -> str | None:
    lsl, usl = characteristic.lsl, characteristic.usl
    if quantity == "pull_force":
        if lsl is None or lsl < condition.pull_force_min_n - 1e-9:
            return f"{characteristic.id} lsl {lsl} below {condition.pull_force_min_n:g} N"
        return None
    low = condition.crimp_height_mm - condition.crimp_height_tol_mm
    high = condition.crimp_height_mm + condition.crimp_height_tol_mm
    if lsl is None or usl is None or lsl < low - 1e-9 or usl > high + 1e-9:
        return f"{characteristic.id} [{lsl}, {usl}] mm looser than [{low:g}, {high:g}] mm"
    return None


def _crimp_checks(
    contract: ProdengContract, imported: ImportRef, contract_dir: Path
) -> list[GateCheck]:
    """Every wire crimp condition is held by height and pull-force inspections on a harness op."""
    gate = "wire.crimp"
    path = Path(imported.path)
    if not path.is_absolute():
        path = contract_dir / path
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return [_check(gate, imported.path, "unknown", detail=f"artifact unreadable: {exc}")]
    if hashlib.sha256(raw).hexdigest() != imported.sha256:
        return [_check(gate, imported.path, "fail", detail="artifact changed since import")]
    try:
        table = WireCrimpSource.model_validate_json(raw)
    except ValidationError as exc:
        return [_check(gate, imported.path, "fail", detail=f"malformed artifact: {exc}")]
    if table.verdict != "pass":
        return [
            _check(
                gate,
                imported.path,
                "unknown",
                detail=f"wire crimp table is incomplete: {', '.join(table.unknown)}",
            )
        ]
    operations = {op.id: op for op in contract.operations}
    characteristics = sorted(contract.characteristics, key=lambda item: item.id)
    known = {condition.id for condition in table.conditions}
    checks: list[GateCheck] = [
        _check(
            gate,
            item.id,
            "fail",
            detail=f"{item.crimp.condition} is not in {table.contract_id}",
        )
        for item in characteristics
        if item.crimp is not None and item.crimp.condition not in known
    ]
    for condition in table.conditions:
        for quantity in ("crimp_height", "pull_force"):
            bound = [
                item
                for item in characteristics
                if item.crimp is not None
                and item.crimp.condition == condition.id
                and item.crimp.quantity == quantity
            ]
            problems: list[str] = []
            held: list[str] = []
            for characteristic in bound:
                problem = _crimp_limit_problem(characteristic, condition, quantity)
                if problem is not None:
                    problems.append(problem)
                inspections = sorted(
                    inspection.id
                    for inspection in contract.inspections
                    if inspection.characteristic == characteristic.id
                    and operations[inspection.operation].kind == "harness"
                )
                if inspections:
                    held.append(f"{characteristic.id} by {', '.join(inspections)}")
                else:
                    problems.append(f"{characteristic.id} is not inspected on a harness operation")
            if not bound:
                problems.append(f"no characteristic controls {quantity}")
            checks.append(
                _check(
                    gate,
                    f"{condition.id}:{quantity}",
                    "fail" if problems else "pass",
                    len(condition.ends),
                    CRIMP_UNITS[quantity],
                    "; ".join(problems) if problems else "; ".join(held),
                )
            )
    return checks


def _formboard_check(
    contract: ProdengContract, imported: ImportRef, contract_dir: Path
) -> GateCheck:
    """A harness operation lays the wires on the board built from the wire formboard."""
    gate = "wire.formboard"
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
        board = WireFormboardSource.model_validate_json(raw)
    except ValidationError as exc:
        return _check(gate, imported.path, "fail", detail=f"malformed artifact: {exc}")
    if board.short:
        return _check(
            gate,
            board.contract_id,
            "fail",
            detail=f"wires shorter than their route: {', '.join(board.short)}",
        )
    if board.verdict != "pass":
        return _check(
            gate,
            board.contract_id,
            "unknown",
            detail=f"wire formboard is incomplete: {', '.join(board.unknown)}",
        )
    fixture = f"formboard:{board.contract_id}"
    holders = sorted(
        op.id for op in contract.operations if op.kind == "harness" and fixture in op.fixtures
    )
    longest = max(route.length_mm for route in board.routes)
    if not holders:
        return _check(
            gate,
            board.contract_id,
            "fail",
            longest,
            "mm",
            f"no harness operation lists fixture {fixture}",
        )
    routes = ", ".join(f"{route.id} {route.length_mm:g} mm" for route in board.routes)
    return _check(
        gate, board.contract_id, "pass", longest, "mm", f"{routes} on {', '.join(holders)}"
    )


def _ebom_check(contract: ProdengContract, contract_dir: Path) -> GateCheck:
    """Every declared EBOM source is imported once, unchanged and readable as a BOM."""
    ebom = product_ebom(contract, contract_dir)
    status = cast(GateStatus, ebom["verdict"])
    lines = cast(list[object], ebom["lines"])
    problems = [*cast(list[str], ebom["failed"]), *cast(list[str], ebom["unknown"])]
    detail = "; ".join(problems) or f"{len(lines)} lines from {', '.join(contract.ebom_sources)}"
    return _check("ebom.complete", contract.product.name, status, len(lines), "lines", detail)


def _continuity_check(
    contract: ProdengContract, imported: ImportRef, contract_dir: Path
) -> GateCheck:
    """Every harness unit gets a 100% continuity/isolation test on the wire table."""
    gate = "wire.continuity"
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
        table = WireContinuitySource.model_validate_json(raw)
    except ValidationError as exc:
        return _check(gate, imported.path, "fail", detail=f"malformed artifact: {exc}")
    if table.verdict != "pass":
        return _check(
            gate,
            table.contract_id,
            "unknown",
            detail=f"wire continuity table is incomplete: {', '.join(table.unknown)}",
        )
    points = sum(len(group.points) for group in table.groups)
    bound = {c.id for c in contract.characteristics if c.continuity}
    kinds = {op.id: op.kind for op in contract.operations}
    holders = sorted(
        f"{item.id} on {item.operation}"
        for item in contract.inspections
        if item.characteristic in bound
        and item.sampling.mode == "full"
        and kinds.get(item.operation) in {"harness", "test"}
    )
    if not holders:
        return _check(
            gate,
            table.contract_id,
            "fail",
            points,
            "points",
            "no 100% inspection of a continuity characteristic on a harness or test operation",
        )
    return _check(
        gate,
        table.contract_id,
        "pass",
        points,
        "points",
        f"{len(table.groups)} conductor groups by {', '.join(holders)}",
    )


STANDARD_GRAVITY = 9.80665


def _packaging_fit(contract: ProdengContract, contract_dir: Path) -> GateCheck:
    """The packed block of units plus cushion fits the carton on every axis."""
    gate = "packaging.fit"
    packaging = contract.packaging
    assert packaging is not None
    subject = contract.product.name
    briefs = [item for item in contract.imports if item.kind == "mech-brief"]
    if not briefs:
        return _check(gate, subject, "unknown", detail="no mech-brief import gives the envelope")
    if len(briefs) > 1:
        paths = ", ".join(sorted(item.path for item in briefs))
        return _check(gate, subject, "fail", detail=f"ambiguous product envelope: {paths}")
    imported = briefs[0]
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
        document: object = json.loads(raw)
        payload = cast(dict[str, object], document) if isinstance(document, dict) else {}
        envelope = mech_envelope_mm(payload)
    except (ValueError, UnicodeDecodeError) as exc:
        return _check(gate, imported.path, "fail", detail=f"malformed artifact: {exc}")
    slack: list[float] = []
    evidence: list[str] = []
    for axis, size, count, inner in zip(
        "xyz", envelope, packaging.arrangement, packaging.carton_inner_mm, strict=True
    ):
        need = round(count * size + 2 * packaging.cushion_mm, 6)
        slack.append(round(inner - need, 6))
        evidence.append(
            f"{axis}: {count} x {size:g} + 2 x {packaging.cushion_mm:g} = {need:g} <= {inner:g}"
        )
    worst = min(slack)
    return _check(
        gate, subject, "pass" if worst >= 0 else "fail", worst, "slack mm >= 0", "; ".join(evidence)
    )


def _ux_in_box(contract: ProdengContract, contract_dir: Path) -> list[str] | GateCheck:
    """In-box item ids, in UX unboxing order, from the single pinned ux-contract import."""
    gate = "packaging.oobe"
    uxs = [item for item in contract.imports if item.kind == "ux-contract"]
    if not uxs:
        return _check(gate, contract.product.name, "unknown", detail="no ux-contract import")
    if len(uxs) > 1:
        paths = ", ".join(sorted(item.path for item in uxs))
        return _check(gate, contract.product.name, "fail", detail=f"ambiguous UX contract: {paths}")
    imported = uxs[0]
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
        document: object = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        return _check(gate, imported.path, "fail", detail=f"malformed artifact: {exc}")
    oobe = cast(dict[str, object], document).get("oobe") if isinstance(document, dict) else None
    items = cast(dict[str, object], oobe).get("in_box") if isinstance(oobe, dict) else None
    if not items:
        return _check(gate, imported.path, "unknown", detail="UX contract declares no oobe.in_box")
    if not isinstance(items, list):
        return _check(gate, imported.path, "fail", detail="malformed oobe.in_box")
    ids: list[str] = []
    for item in cast(list[object], items):
        item_id = cast(dict[str, object], item).get("id") if isinstance(item, dict) else None
        if not isinstance(item_id, str) or not item_id or item_id in ids:
            return _check(gate, imported.path, "fail", detail="malformed oobe.in_box")
        ids.append(item_id)
    return ids


def _packaging_oobe(contract: ProdengContract, contract_dir: Path) -> GateCheck:
    """Every UX in-box item is packed once, by a packing operation, in unboxing order."""
    packaging = contract.packaging
    assert packaging is not None
    ux_ids = _ux_in_box(contract, contract_dir)
    if isinstance(ux_ids, GateCheck):
        return ux_ids
    if packaging.contents is None:
        return _check(
            "packaging.oobe", contract.product.name, "fail", detail="packaging.contents missing"
        )
    packed = {item.id: item for item in packaging.contents}
    packers = {op.id for op in contract.operations if op.kind == "packing"}
    problems = [f"{item_id} not packed" for item_id in ux_ids if item_id not in packed]
    problems += [f"{item_id} not in the UX box" for item_id in sorted(set(packed) - set(ux_ids))]
    problems += [
        f"{item.id}: {item.operation} is not a packing operation"
        for item in packaging.contents
        if item.operation not in packers
    ]
    order = [packed[item_id] for item_id in ux_ids if item_id in packed]
    problems += [
        f"{later.id} (layer {later.layer}) above {earlier.id} (layer {earlier.layer})"
        for earlier, later in pairwise(order)
        if later.layer < earlier.layer
    ]
    return _check(
        "packaging.oobe",
        contract.product.name,
        "fail" if problems else "pass",
        len(problems),
        0,
        "; ".join(problems) or f"{len(ux_ids)} items packed in unboxing order",
    )


def _packaging_checks(contract: ProdengContract, contract_dir: Path) -> list[GateCheck]:
    packaging = contract.packaging
    assert packaging is not None
    subject = contract.product.name
    gross = packaging.gross_kg
    checks = [
        _packaging_fit(contract, contract_dir),
        _check(
            "packaging.mass",
            subject,
            "pass" if gross <= packaging.max_gross_kg else "fail",
            gross,
            packaging.max_gross_kg,
            f"{packaging.units} x {packaging.unit_mass_kg:g} kg"
            f" + {packaging.packaging_mass_kg:g} kg packaging; limit from {packaging.source}",
        ),
    ]
    pallet = packaging.pallet
    if pallet is not None:
        load = round((pallet.layers - 1) * gross * STANDARD_GRAVITY * pallet.safety_factor, 6)
        checks.append(
            _check(
                "packaging.stack",
                subject,
                "pass" if load <= pallet.box_compression_n else "fail",
                load,
                pallet.box_compression_n,
                f"{pallet.layers - 1} cartons of {gross:g} kg above the bottom one x safety "
                f"{pallet.safety_factor:g}; BCT from {pallet.source}",
            )
        )
    packers = sorted(op.id for op in contract.operations if op.kind == "packing")
    checks.append(
        _check(
            "packaging.operation",
            subject,
            "pass" if packers else "fail",
            len(packers),
            ">= 1 packing operation",
            ", ".join(packers) or "no operation packs the carton",
        )
    )
    if packaging.contents is not None or any(
        item.kind == "ux-contract" for item in contract.imports
    ):
        checks.append(_packaging_oobe(contract, contract_dir))
    return checks


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


def _appearance_checks(
    contract: ProdengContract, imported: ImportRef, contract_dir: Path
) -> list[GateCheck]:
    """Every class A/B defect limit is judged by a visual inspection holding its sample pair."""
    gate = "appearance.limit_samples"
    path = Path(imported.path)
    if not path.is_absolute():
        path = contract_dir / path
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return [_check(gate, imported.path, "unknown", detail=f"artifact unreadable: {exc}")]
    if hashlib.sha256(raw).hexdigest() != imported.sha256:
        return [_check(gate, imported.path, "fail", detail="artifact changed since import")]
    try:
        artifact = MechAppearanceSource.model_validate_json(raw)
    except ValidationError as exc:
        return [_check(gate, imported.path, "fail", detail=f"malformed artifact: {exc}")]
    viewing = artifact.viewing
    condition = (
        f"{viewing.distance_mm:g} mm, {viewing.illuminance_lux:g} lx, {viewing.time_s:g} s, "
        f"{viewing.angle_deg:g} deg ({viewing.source})"
    )
    characteristics = {item.id: item for item in contract.characteristics}
    checks: list[GateCheck] = []
    for surface in sorted(artifact.surfaces, key=lambda item: item.face):
        for limit in sorted(surface.defects, key=lambda item: item.defect):
            subject = f"{artifact.design}:{surface.face}:{limit.defect}"
            sides = {
                sample.side: sample.id
                for sample in artifact.samples
                if sample.face == surface.face and sample.defect == limit.defect
            }
            pair = sorted(
                sample.side
                for sample in artifact.samples
                if sample.face == surface.face and sample.defect == limit.defect
            )
            if surface.cosmetic_class == "C" and not pair:
                continue
            if pair != ["accept", "reject"]:
                checks.append(
                    _check(
                        gate,
                        subject,
                        "fail",
                        detail=f"class {surface.cosmetic_class} limit lacks an accept/reject "
                        f"sample pair (has {pair or 'none'})",
                    )
                )
                continue
            needed = {sides["accept"], sides["reject"]}
            holders = sorted(
                (
                    inspection
                    for inspection in contract.inspections
                    if needed.issubset(inspection.limit_samples)
                ),
                key=lambda item: item.id,
            )
            label = f"{sides['accept']} (accept) / {sides['reject']} (reject)"
            if not holders:
                checks.append(
                    _check(
                        gate,
                        subject,
                        "fail",
                        detail=f"no visual inspection holds {label}",
                    )
                )
                continue
            variable = [
                item.id
                for item in holders
                if characteristics[item.characteristic].kind != "attribute"
            ]
            if variable:
                checks.append(
                    _check(
                        gate,
                        subject,
                        "fail",
                        detail=f"{', '.join(variable)} judge a limit sample on a variable "
                        "characteristic; limit samples need an attribute characteristic",
                    )
                )
                continue
            checks.append(
                _check(
                    gate,
                    subject,
                    "pass",
                    measured=", ".join(item.id for item in holders),
                    limit=limit.bound(),
                    detail=f"class {surface.cosmetic_class}; {label}; viewing {condition}",
                )
            )
    if not checks:
        checks.append(
            _check(gate, imported.path, "pass", detail="class C only; no limit samples required")
        )
    return checks


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


GRR_PCT_MAX = {"critical": 10.0, "major": 30.0, "minor": 30.0}
CPK_MIN = {"critical": 1.67, "major": 1.33, "minor": 1.33}
RESOLUTION_RATIO = 10


def _msa_checks(contract: ProdengContract) -> list[GateCheck]:
    """AIAG MSA/PPAP planning limits on declared gauges and capability targets."""
    characteristics = {item.id: item for item in contract.characteristics}
    checks: list[GateCheck] = []
    for inspection in sorted(contract.inspections, key=lambda item: item.id):
        gauge = inspection.gauge
        characteristic = characteristics.get(inspection.characteristic)
        if gauge is None or characteristic is None:
            continue
        if characteristic.kind != "variable":
            checks.append(
                _check(
                    "msa.resolution",
                    inspection.id,
                    "fail",
                    detail=f"gauge declared for attribute characteristic {characteristic.id}",
                )
            )
            continue
        if characteristic.lsl is None or characteristic.usl is None:
            checks.append(
                _check(
                    "msa.resolution",
                    inspection.id,
                    "unknown",
                    gauge.resolution,
                    _window(characteristic),
                    "the 10:1 rule needs a two-sided tolerance",
                )
            )
        else:
            limit = round((characteristic.usl - characteristic.lsl) / RESOLUTION_RATIO, 12)
            checks.append(
                _check(
                    "msa.resolution",
                    inspection.id,
                    "pass" if gauge.resolution <= limit else "fail",
                    gauge.resolution,
                    f"<= {limit:g} {characteristic.unit} (tolerance/10)",
                    f"{characteristic.id} gauge per {gauge.source}",
                )
            )
        grr_limit = GRR_PCT_MAX[characteristic.classification]
        checks.append(
            _check(
                "msa.grr",
                inspection.id,
                "pass" if gauge.grr_pct_max <= grr_limit else "fail",
                gauge.grr_pct_max,
                f"<= {grr_limit:g} % for {characteristic.classification}",
                f"{characteristic.id} %GRR per {gauge.source}",
            )
        )
    for characteristic in sorted(contract.characteristics, key=lambda item: item.id):
        if characteristic.cpk_min is None:
            continue
        cpk_limit = CPK_MIN[characteristic.classification]
        checks.append(
            _check(
                "capability.cpk_target",
                characteristic.id,
                "pass" if characteristic.cpk_min >= cpk_limit else "fail",
                characteristic.cpk_min,
                f">= {cpk_limit:g} for {characteristic.classification}",
                "capability target the control plan holds the process to",
            )
        )
    return checks


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
