from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from prodeng.contract import ProdengContract, load_contract
from prodeng.gates import GateCheck, run_gates
from prodeng.imports import extract_import, import_source

EXAMPLE = Path(__file__).parents[1] / "examples" / "smart-kettle"
FIXTURE = Path(__file__).parent / "fixtures" / "upstream" / "smart-kettle.circuit-assembly.json"


def _artifact(**changes: Any) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data.update(changes)
    return data


def _sides(contract: ProdengContract, sides: dict[str, list[str]]) -> ProdengContract:
    data = contract.model_dump(mode="json")
    for operation in data["operations"]:
        operation["sides"] = sides.get(operation["id"], [])
    return ProdengContract.model_validate(data)


def _imported(
    tmp_path: Path, artifact: dict[str, Any], sides: dict[str, list[str]] | None = None
) -> tuple[ProdengContract, Path, Path]:
    shutil.copytree(EXAMPLE, tmp_path / "smart-kettle")
    contract_path = tmp_path / "smart-kettle" / "smart-kettle.prodeng.json"
    path = contract_path.parent / "upstream" / "smart-kettle.circuit-assembly.json"
    path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    contract = import_source(
        load_contract(contract_path), "circuit-assembly", path, contract_path.parent
    )
    bound = {"OP01": ["top"], "OP02": ["top"]} if sides is None else sides
    return _sides(contract, bound), contract_path.parent, path


def _checks(contract: ProdengContract, contract_dir: Path) -> dict[str, GateCheck]:
    report = run_gates(contract, contract_dir)
    return {c.subject: c for c in report.checks if c.id == "circuit.assembly"}


def test_real_circuit_agent_export_imports_populated_parts() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert extract_import("circuit-assembly", payload).parts == ["C1", "J1", "R1", "U1"]


def test_every_mount_and_side_group_is_placed(tmp_path: Path) -> None:
    contract, contract_dir, _ = _imported(tmp_path, _artifact())
    checks = _checks(contract, contract_dir)
    assert set(checks) == {"smd:top", "tht:top", "brief:upstream/smart-kettle.circuit-brief.json"}
    assert all(check.status == "pass" for check in checks.values()), checks
    assert checks["smd:top"].detail == "OP01 places C1, R1"
    assert checks["smd:top"].measured == 2
    assert checks["tht:top"].detail == "OP02 places J1, U1"


def test_unbound_side_fails(tmp_path: Path) -> None:
    contract, contract_dir, _ = _imported(tmp_path, _artifact(), {"OP01": ["top"]})
    check = _checks(contract, contract_dir)["tht:top"]
    assert check.status == "fail" and check.detail == "no operation places J1, U1"
    assert run_gates(contract, contract_dir).verdict == "fail"


def test_bottom_side_part_needs_its_own_side(tmp_path: Path) -> None:
    artifact = _artifact()
    for item in artifact["placements"]:
        if item["ref"] == "C1":
            item["side"] = "bottom"
    contract, contract_dir, _ = _imported(tmp_path, artifact)
    checks = _checks(contract, contract_dir)
    assert checks["smd:bottom"].status == "fail" and checks["smd:top"].status == "pass"


def test_dnp_parts_are_not_placed(tmp_path: Path) -> None:
    contract, contract_dir, _ = _imported(tmp_path, _artifact())
    assert "R2" not in _checks(contract, contract_dir)["smd:top"].detail


def test_brief_part_missing_from_board_fails(tmp_path: Path) -> None:
    artifact = _artifact()
    artifact["placements"] = [p for p in artifact["placements"] if p["ref"] != "U1"]
    contract, contract_dir, _ = _imported(tmp_path, artifact)
    check = _checks(contract, contract_dir)["brief:upstream/smart-kettle.circuit-brief.json"]
    assert check.status == "fail" and check.detail == "board does not place U1"


def test_incomplete_export_is_unknown(tmp_path: Path) -> None:
    contract, contract_dir, path = _imported(
        tmp_path, _artifact(verdict="fail", unknown=["mount:U9"])
    )
    check = _checks(contract, contract_dir)[str(path.relative_to(contract_dir))]
    assert check.status == "unknown" and "mount:U9" in check.detail


def test_changed_or_missing_artifact(tmp_path: Path) -> None:
    contract, contract_dir, path = _imported(tmp_path, _artifact())
    subject = str(path.relative_to(contract_dir))
    path.write_text(json.dumps(_artifact(placements=[])), encoding="utf-8")
    assert _checks(contract, contract_dir)[subject].status == "fail"
    path.write_text("{", encoding="utf-8")
    assert _checks(contract, contract_dir)[subject].status == "fail"
    path.unlink()
    assert _checks(contract, contract_dir)[subject].status == "unknown"


@pytest.mark.parametrize(
    "changes",
    [
        {"artifact_kind": "circuit_board_geometry"},
        {"verdict": "pass", "unknown": ["mount:U9"]},
        {"verdict": "fail", "unknown": []},
        {"extra": True},
    ],
)
def test_malformed_artifact_is_rejected_on_import(tmp_path: Path, changes: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="circuit-assembly"):
        _imported(tmp_path, _artifact(**changes))


def test_duplicate_reference_is_rejected() -> None:
    payload = _artifact()
    payload["placements"].append(dict(payload["placements"][0]))
    with pytest.raises(ValueError, match="repeat"):
        extract_import("circuit-assembly", payload)


@pytest.mark.parametrize(
    ("sides", "message"),
    [({"OP03": ["top"]}, "not smt/tht"), ({"OP01": ["top", "top"]}, "side twice")],
)
def test_sides_only_on_assembly_operations(
    tmp_path: Path, sides: dict[str, list[str]], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        _imported(tmp_path, _artifact(), sides)
