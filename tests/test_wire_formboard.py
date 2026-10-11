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
FIXTURE = Path(__file__).parent / "fixtures" / "upstream" / "WH-0001.wire-formboard.json"


def _artifact(**changes: Any) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data.update(changes)
    return data


def _setup(tmp_path: Path, artifact: dict[str, Any]) -> tuple[ProdengContract, Path, Path]:
    shutil.copytree(EXAMPLE, tmp_path / "smart-kettle")
    contract_path = tmp_path / "smart-kettle" / "smart-kettle.prodeng.json"
    path = contract_path.parent / "upstream" / "WH-0001.wire-formboard.json"
    path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    contract = import_source(
        load_contract(contract_path), "wire-formboard", path, contract_path.parent
    )
    return contract, contract_path.parent, path


def _with_op(contract: ProdengContract, kind: str = "harness", fixture: str = "formboard:WH-0001"):
    data = contract.model_dump(mode="json")
    data["operations"].append(
        {
            "id": "OP08",
            "name": "Lay harness",
            "kind": kind,
            "station": "ST8",
            "operators": 1,
            "fixtures": [fixture],
        }
    )
    return ProdengContract.model_validate(data)


def _check(contract: ProdengContract, root: Path) -> GateCheck:
    checks = [c for c in run_gates(contract, root).checks if c.id == "wire.formboard"]
    assert len(checks) == 1
    return checks[0]


def test_real_artifact_imports() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert extract_import("wire-formboard", payload) is not None


def test_board_on_harness_operation_passes(tmp_path: Path) -> None:
    contract, root, _ = _setup(tmp_path, _artifact())
    check = _check(_with_op(contract), root)
    assert check.status == "pass" and check.measured == 550.0 and "OP08" in check.detail


@pytest.mark.parametrize(
    ("kind", "fixture"), [("harness", "formboard:WH-9999"), ("inspection", "formboard:WH-0001")]
)
def test_board_not_held_by_harness_operation_fails(tmp_path: Path, kind: str, fixture: str) -> None:
    contract, root, _ = _setup(tmp_path, _artifact())
    assert _check(_with_op(contract, kind, fixture), root).status == "fail"
    assert _check(contract, root).status == "fail"


def test_short_wire_fails(tmp_path: Path) -> None:
    data = _artifact()
    data["routes"][0]["wires"][0]["slack_mm"] = -1.0
    data["short"] = [data["routes"][0]["wires"][0]["id"]]
    data["verdict"] = "fail"
    contract, root, _ = _setup(tmp_path, data)
    assert _check(_with_op(contract), root).status == "fail"


def test_board_without_routes_is_unknown(tmp_path: Path) -> None:
    contract, root, _ = _setup(
        tmp_path, _artifact(routes=[], unrouted=[], unknown=["routes"], verdict="fail")
    )
    assert _check(_with_op(contract), root).status == "unknown"


def test_changed_and_missing_artifacts(tmp_path: Path) -> None:
    contract, root, path = _setup(tmp_path, _artifact())
    contract = _with_op(contract)
    path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    assert _check(contract, root).status == "fail"
    path.unlink()
    assert _check(contract, root).status == "unknown"


@pytest.mark.parametrize(
    "changes",
    [
        {"verdict": "fail"},
        {"short": ["W1"]},
        {"artifact_kind": "wire_crimp"},
        {"extra": 1},
    ],
)
def test_malformed_artifacts_are_rejected(changes: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="malformed wire-formboard"):
        extract_import("wire-formboard", _artifact(**changes))
