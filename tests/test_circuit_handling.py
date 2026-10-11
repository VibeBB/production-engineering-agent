from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from prodeng.contract import ProdengContract, load_contract
from prodeng.gates import GateCheck, run_gates
from prodeng.imports import extract_import, import_source

EXAMPLE = Path(__file__).parents[1] / "examples" / "smart-kettle"
FIXTURE = Path(__file__).parent / "fixtures" / "upstream" / "smart-kettle.circuit-handling.json"
GOOD = {"OP01": {"esd_sensitive": True, "reflow_peak_c": 245, "floor_life_control": True}}


def _artifact() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _ops(contract: ProdengContract, changes: dict[str, dict[str, Any]]) -> ProdengContract:
    data = contract.model_dump(mode="json")
    for operation in data["operations"]:
        if operation["kind"] in {"smt", "tht", "selective_solder"}:
            operation["esd_sensitive"] = True
        operation.update(changes.get(operation["id"], {}))
    return ProdengContract.model_validate(data)


def _imported(
    tmp_path: Path, artifact: dict[str, Any], changes: dict[str, dict[str, Any]] | None = None
) -> tuple[ProdengContract, Path, Path]:
    shutil.copytree(EXAMPLE, tmp_path / "smart-kettle")
    contract_path = tmp_path / "smart-kettle" / "smart-kettle.prodeng.json"
    path = contract_path.parent / "upstream" / "smart-kettle.circuit-handling.json"
    path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    contract = import_source(
        load_contract(contract_path), "circuit-handling", path, contract_path.parent
    )
    return _ops(contract, GOOD if changes is None else changes), contract_path.parent, path


def _checks(contract: ProdengContract, contract_dir: Path) -> dict[str, GateCheck]:
    report = run_gates(contract, contract_dir)
    return {c.subject: c for c in report.checks if c.id == "circuit.handling"}


def test_real_circuit_agent_export_imports_handled_parts() -> None:
    assert extract_import("circuit-handling", _artifact()).parts == ["J1", "U1"]


def test_controlled_operations_pass(tmp_path: Path) -> None:
    checks = _checks(*_imported(tmp_path, _artifact())[:2])
    assert set(checks) == {"esd", "reflow:OP01", "msl"}
    assert all(c.status == "pass" for c in checks.values()), checks


@pytest.mark.parametrize(("peak", "status"), [(260, "pass"), (260.1, "fail"), (None, "unknown")])
def test_reflow_peak_boundary(tmp_path: Path, peak: float | None, status: str) -> None:
    changes = {"OP01": {**GOOD["OP01"], "reflow_peak_c": peak}}
    check = _checks(*_imported(tmp_path, _artifact(), changes)[:2])["reflow:OP01"]
    assert check.status == status and check.limit == 260


def test_operation_without_esd_control_fails(tmp_path: Path) -> None:
    contract, contract_dir, _ = _imported(tmp_path, _artifact())
    data = contract.model_dump(mode="json")
    data["operations"][0]["esd_sensitive"] = False
    check = _checks(ProdengContract.model_validate(data), contract_dir)["esd"]
    assert check.status == "fail" and "without ESD control" in check.detail


def test_msl_without_floor_life_control_fails(tmp_path: Path) -> None:
    changes = {"OP01": {**GOOD["OP01"], "floor_life_control": False}}
    check = _checks(*_imported(tmp_path, _artifact(), changes)[:2])["msl"]
    assert check.status == "fail" and "U1" in check.detail


def test_msl1_and_esd_safe_parts_need_no_controls(tmp_path: Path) -> None:
    artifact = _artifact()
    for item in artifact["parts"]:
        item.update(msl="1", esd_sensitive=False)
    changes = {"OP01": {"reflow_peak_c": 245}}
    assert set(_checks(*_imported(tmp_path, artifact, changes)[:2])) == {"reflow:OP01"}


def test_changed_artifact_fails(tmp_path: Path) -> None:
    contract, contract_dir, path = _imported(tmp_path, _artifact())
    path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    assert (
        _checks(contract, contract_dir)[path.relative_to(contract_dir).as_posix()].status == "fail"
    )


def test_missing_artifact_is_unknown(tmp_path: Path) -> None:
    contract, contract_dir, path = _imported(tmp_path, _artifact())
    path.unlink()
    assert {c.status for c in _checks(contract, contract_dir).values()} == {"unknown"}


def test_incomplete_export_is_unknown(tmp_path: Path) -> None:
    artifact = _artifact()
    artifact.update(unknown=["R1"], verdict="unknown")
    check = next(iter(_checks(*_imported(tmp_path, artifact)[:2]).values()))
    assert check.status == "unknown" and "R1" in check.detail


@pytest.mark.parametrize(
    "change",
    [
        {"verdict": "unknown"},
        {"artifact_kind": "circuit_assembly"},
        {"extra": 1},
    ],
)
def test_malformed_export_is_rejected_on_import(tmp_path: Path, change: dict[str, Any]) -> None:
    artifact = {**_artifact(), **change}
    with pytest.raises(ValueError, match="malformed circuit-handling"):
        _imported(tmp_path, artifact)


def test_repeated_part_is_rejected() -> None:
    artifact = _artifact()
    artifact["parts"].append(artifact["parts"][0])
    with pytest.raises(ValueError, match="repeat"):
        extract_import("circuit-handling", artifact)
