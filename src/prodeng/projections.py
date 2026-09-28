"""Stable, deterministic manufacturing-plan projections."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from .contract import Inspection, Operation, ProdengContract
from .sampling import sampling_plan


def _json_write(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _csv_write(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def _sample_record(contract: ProdengContract, inspection: Inspection) -> dict[str, Any]:
    sampling = inspection.sampling
    record: dict[str, Any] = {
        "inspection": inspection.id,
        "mode": sampling.mode,
        "aql": sampling.aql,
        "level": sampling.level,
    }
    if sampling.mode == "full":
        record.update(
            {
                "code_letter": None,
                "sample_size": contract.volume.lot_size,
                "accept": 0,
                "reject": 1,
                "full_inspection": True,
            }
        )
        return record
    if sampling.aql is None:
        record["error"] = "AQL value is missing"
        return record
    try:
        plan = sampling_plan(contract.volume.lot_size, sampling.aql, sampling.level)
    except ValueError as exc:
        record["error"] = str(exc)
        return record
    record.update(
        {
            "table_letter": plan.table_letter,
            "code_letter": plan.code_letter,
            "sample_size": plan.sample_size,
            "accept": plan.accept,
            "reject": plan.reject,
            "full_inspection": plan.full_inspection,
        }
    )
    return record


def _write_control_plan(contract: ProdengContract, path: Path) -> None:
    characteristics = {item.id: item for item in contract.characteristics}
    operations = {item.id: item for item in contract.operations}
    rows = [
        [
            characteristic.id,
            characteristic.description,
            characteristic.classification,
            operation.id,
            operation.name,
            inspection.method,
            inspection.sampling.mode,
            str(inspection.sampling.aql or ""),
            inspection.sampling.level,
            inspection.equipment,
            inspection.reaction_plan,
        ]
        for inspection in sorted(contract.inspections, key=lambda item: item.id)
        for characteristic in [characteristics[inspection.characteristic]]
        for operation in [operations[inspection.operation]]
    ]
    _csv_write(
        path,
        [
            "characteristic_id",
            "characteristic",
            "classification",
            "operation_id",
            "operation",
            "method",
            "sampling_mode",
            "aql",
            "level",
            "equipment",
            "reaction_plan",
        ],
        rows,
    )


def _write_inspection_plan(contract: ProdengContract, out_dir: Path) -> None:
    inspections = sorted(contract.inspections, key=lambda item: item.id)
    _json_write(
        out_dir / "inspection-plan.json",
        [
            {
                "inspection_id": inspection.id,
                "characteristic_id": inspection.characteristic,
                "operation_id": inspection.operation,
                "method": inspection.method,
                "equipment": inspection.equipment,
                "reaction_plan": inspection.reaction_plan,
                "ftm_commands": sorted(inspection.ftm_commands),
                "sampling": _sample_record(contract, inspection),
            }
            for inspection in inspections
        ],
    )
    _json_write(
        out_dir / "sampling-plans.json",
        [
            _sample_record(contract, inspection)
            for inspection in inspections
            if inspection.sampling.mode == "aql"
        ],
    )


def _write_line_balance(contract: ProdengContract, path: Path) -> None:
    stations: dict[str, list[Operation]] = {}
    for operation in contract.operations:
        stations.setdefault(operation.station, []).append(operation)
    rows: list[list[str]] = []
    for station, operations in sorted(
        stations.items(),
        key=lambda item: min(operation.id for operation in item[1]),
    ):
        cycle_times = [operation.cycle_time_s for operation in operations]
        total = (
            sum(value for value in cycle_times if value is not None)
            if all(value is not None for value in cycle_times)
            else None
        )
        rows.append(
            [
                station,
                "; ".join(
                    operation.id for operation in sorted(operations, key=lambda item: item.id)
                ),
                "; ".join(sorted({operation.name for operation in operations})),
                "" if total is None else f"{total:g}",
                f"{contract.volume.takt_s:g}",
                "" if total is None else f"{total / contract.volume.takt_s:.6f}",
                "; ".join(
                    str(operation.operators)
                    for operation in sorted(operations, key=lambda item: item.id)
                ),
            ]
        )
    _csv_write(
        path,
        [
            "station",
            "operation_ids",
            "operations",
            "cycle_time_s",
            "takt_s",
            "utilization",
            "operators_by_operation",
        ],
        rows,
    )


def _write_pfmea(contract: ProdengContract, path: Path) -> None:
    rows = [
        [
            item.id,
            item.operation,
            item.mode,
            item.effect,
            item.cause,
            str(item.severity),
            str(item.occurrence),
            str(item.detection),
            str(item.severity * item.occurrence * item.detection),
            "; ".join(sorted(item.controls)),
        ]
        for item in sorted(contract.failure_modes, key=lambda entry: entry.id)
    ]
    _csv_write(
        path,
        [
            "failure_mode_id",
            "operation_id",
            "failure_mode",
            "effect",
            "cause",
            "severity",
            "occurrence",
            "detection",
            "rpn_informational",
            "controls",
        ],
        rows,
    )


def _markdown_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    return [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *(
            "| " + " | ".join(value.replace("|", "\\|").replace("\n", " ") for value in row) + " |"
            for row in rows
        ),
    ]


def _write_work_instructions(contract: ProdengContract, path: Path) -> None:
    lines = [
        f"# Work instructions — {contract.product.name}",
        "",
        f"Revision: {contract.product.revision}",
        "",
    ]
    inspection_by_operation: dict[str, list[str]] = {}
    for inspection in contract.inspections:
        inspection_by_operation.setdefault(inspection.operation, []).append(
            f"{inspection.id} ({inspection.method}, {inspection.characteristic})"
        )
    for operation in sorted(contract.operations, key=lambda item: item.id):
        linked_inspections = sorted(inspection_by_operation.get(operation.id, []))
        cycle_time = operation.cycle_time_s if operation.cycle_time_s is not None else "unknown"
        lines.extend(
            [
                f"## {operation.id} — {operation.name}",
                "",
                f"Station: {operation.station}",
                f"Cycle time: {cycle_time} s",
                f"Operators: {operation.operators}",
                f"Tools: {', '.join(sorted(operation.tools)) or 'None specified'}",
                f"Fixtures: {', '.join(sorted(operation.fixtures)) or 'None specified'}",
                "ESD: "
                + (
                    "sensitive; use grounded ESD controls"
                    if operation.esd_sensitive
                    else "not designated"
                ),
                "Safety hazards: " + (", ".join(operation.safety_hazards) or "None specified"),
                "Safety precautions: "
                + (", ".join(operation.safety_precautions) or "None specified"),
                f"Linked inspections: {'; '.join(linked_inspections) or 'None'}",
                "",
                *_markdown_table(
                    ["Major step", "Key points", "Reasons"],
                    [
                        [
                            element.step,
                            "; ".join(element.key_points),
                            "; ".join(element.reasons),
                        ]
                        for element in operation.work_elements
                    ],
                ),
                "",
            ]
        )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _ftm_spec(contract: ProdengContract) -> dict[str, Any]:
    ftm = contract.factory_test_mode
    if ftm is None:
        return {"declared": False, "reason": "No factory_test_mode is declared."}
    return {
        "declared": True,
        "entry": ftm.entry.model_dump(mode="json"),
        "field_lockout": ftm.field_lockout.model_dump(mode="json"),
        "interface": {
            **ftm.interface.model_dump(mode="json"),
            "nets": sorted(ftm.interface.nets),
        },
        "commands": [
            {
                **command.model_dump(mode="json"),
                "covers": sorted(command.covers),
                "measures_nets": sorted(command.measures_nets),
            }
            for command in sorted(ftm.commands, key=lambda item: item.id)
        ],
        "provisioning": [item.model_dump(mode="json") for item in ftm.provisioning],
        "exit": ftm.exit,
        "max_duration_s": ftm.max_duration_s,
        "command_timeout_budget_s": sum(command.timeout_ms for command in ftm.commands) / 1000,
    }


def _write_ftm(contract: ProdengContract, out_dir: Path) -> None:
    spec = _ftm_spec(contract)
    _json_write(out_dir / "factory-test-spec.json", spec)
    lines = [f"# Factory test specification — {contract.product.name}", ""]
    if not spec["declared"]:
        lines.extend([str(spec["reason"]), ""])
    else:
        ftm = contract.factory_test_mode
        if ftm is not None:
            lines.extend(
                [
                    "## Entry",
                    "",
                    f"Method: {ftm.entry.method}",
                    ftm.entry.detail,
                    "",
                    *_markdown_table(
                        ["Guard condition"],
                        [[condition] for condition in ftm.entry.conditions],
                    ),
                    "",
                    "## Field lockout",
                    "",
                    f"{ftm.field_lockout.method}: {ftm.field_lockout.detail}",
                    "",
                    "## Interface",
                    "",
                    f"Transport: {ftm.interface.transport}; settings: {ftm.interface.settings}",
                    f"Nets: {', '.join(sorted(ftm.interface.nets)) or 'None declared'}",
                    "",
                    "## Commands",
                    "",
                    *_markdown_table(
                        ["ID", "Command", "Request", "Response", "Timeout (ms)", "Measures"],
                        [
                            [
                                command.id,
                                command.name,
                                command.request,
                                command.response_pattern,
                                str(command.timeout_ms),
                                ", ".join(sorted(command.measures_nets)),
                            ]
                            for command in sorted(ftm.commands, key=lambda item: item.id)
                        ],
                    ),
                    "",
                    "## Provisioning",
                    "",
                    *_markdown_table(
                        ["Item", "Source", "Write once"],
                        [
                            [item.item, item.source, str(item.write_once).lower()]
                            for item in ftm.provisioning
                        ],
                    ),
                    "",
                    "## Exit",
                    "",
                    ftm.exit,
                    "",
                    "## Duration budget",
                    "",
                    f"Command timeout total: {spec['command_timeout_budget_s']:g} s; "
                    f"maximum: {ftm.max_duration_s:g} s.",
                    "",
                ]
            )
    (out_dir / "factory-test-spec.md").write_text(
        "\n".join(lines).rstrip() + "\n", encoding="utf-8"
    )


def _write_manifest(contract: ProdengContract, out_dir: Path, name: str) -> None:
    files = sorted(
        path.name
        for path in out_dir.iterdir()
        if path.is_file()
        and path.name not in ("manifest.json", "prodeng-report.json", "prodeng-report.md")
    )
    _json_write(
        out_dir / "manifest.json",
        {
            "schema_version": 1,
            "system": "prodeng",
            "product": contract.product.name,
            "revision": contract.product.revision,
            "artifact_stem": name,
            "files": files,
        },
    )


def write_provenance(contract: ProdengContract, out_dir: Path) -> Path:
    path = out_dir / "provenance.json"
    contract_digest = hashlib.sha256(
        json.dumps(contract.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    _json_write(
        path,
        {
            "system": "prodeng",
            "contract_sha256": contract_digest,
            "imports": [
                item.model_dump(mode="json")
                for item in sorted(
                    contract.imports, key=lambda imported: (imported.system, imported.path)
                )
            ],
        },
    )
    return path


def write_projections(contract: ProdengContract, name: str, out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    control_path = out_dir / "control-plan.csv"
    _write_control_plan(contract, control_path)
    _write_inspection_plan(contract, out_dir)
    line_path = out_dir / "line-balance.csv"
    _write_line_balance(contract, line_path)
    pfmea_path = out_dir / "pfmea.csv"
    _write_pfmea(contract, pfmea_path)
    work_path = out_dir / "work-instructions.md"
    _write_work_instructions(contract, work_path)
    _write_ftm(contract, out_dir)
    provenance_path = write_provenance(contract, out_dir)
    _write_manifest(contract, out_dir, name)
    return {
        "control_plan": control_path,
        "inspection_plan": out_dir / "inspection-plan.json",
        "sampling_plans": out_dir / "sampling-plans.json",
        "line_balance": line_path,
        "pfmea": pfmea_path,
        "work_instructions": work_path,
        "factory_test_json": out_dir / "factory-test-spec.json",
        "factory_test_markdown": out_dir / "factory-test-spec.md",
        "manifest": out_dir / "manifest.json",
        "provenance": provenance_path,
    }
