"""wire.continuity: the wire continuity table is tested 100% on a harness/test operation."""

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
FIXTURE = Path(__file__).parent / "fixtures" / "upstream" / "WH-0001.wire-continuity.json"


def _artifact(**changes: Any) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data.update(changes)
    return data


def _setup(tmp_path: Path, artifact: dict[str, Any]) -> tuple[ProdengContract, Path, Path]:
    shutil.copytree(EXAMPLE, tmp_path / "smart-kettle")
    contract_path = tmp_path / "smart-kettle" / "smart-kettle.prodeng.json"
    path = contract_path.parent / "upstream" / "WH-0001.wire-continuity.json"
    path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    contract = import_source(
        load_contract(contract_path), "wire-continuity", path, contract_path.parent
    )
    return contract, contract_path.parent, path


def _bind(
    contract: ProdengContract, *, op_kind: str = "harness", sampling: str = "full"
) -> ProdengContract:
    data = contract.model_dump(mode="json")
    data["operations"].append(
        {"id": "OP09", "name": "Test harness", "kind": op_kind, "station": "ST9", "operators": 1}
    )
    data["characteristics"].append(
        {
            "id": "CH-95",
            "description": "harness continuity and isolation",
            "classification": "critical",
            "kind": "attribute",
            "criterion": "continuity inside each group, isolation between groups",
            "sources": ["R001"],
            "continuity": True,
        }
    )
    data["inspections"].append(
        {
            "id": "IN-95",
            "characteristic": "CH-95",
            "operation": "OP09",
            "method": "measurement",
            "sampling": {"mode": "full"} if sampling == "full" else {"mode": "aql", "aql": 0.65},
            "equipment": "harness continuity tester",
            "reaction_plan": "Quarantine the harness and trace the open or short.",
        }
    )
    return ProdengContract.model_validate(data)


def _check(contract: ProdengContract, root: Path) -> GateCheck:
    checks = [c for c in run_gates(contract, root).checks if c.id == "wire.continuity"]
    assert len(checks) == 1
    return checks[0]


def test_real_artifact_imports() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert extract_import("wire-continuity", payload) is not None


def test_full_continuity_inspection_on_harness_op_passes(tmp_path: Path) -> None:
    contract, root, _ = _setup(tmp_path, _artifact())
    check = _check(_bind(contract), root)
    assert check.status == "pass", check.detail
    assert check.measured == 6
    assert "IN-95 on OP09" in check.detail


def test_test_operation_also_holds_the_test(tmp_path: Path) -> None:
    contract, root, _ = _setup(tmp_path, _artifact())
    assert _check(_bind(contract, op_kind="test"), root).status == "pass"


@pytest.mark.parametrize(("op_kind", "sampling"), [("packing", "full"), ("harness", "aql")])
def test_sampled_or_misplaced_inspection_fails(tmp_path: Path, op_kind: str, sampling: str) -> None:
    contract, root, _ = _setup(tmp_path, _artifact())
    check = _check(_bind(contract, op_kind=op_kind, sampling=sampling), root)
    assert check.status == "fail"
    assert "no 100% inspection" in check.detail


def test_no_continuity_characteristic_fails(tmp_path: Path) -> None:
    contract, root, _ = _setup(tmp_path, _artifact())
    assert _check(contract, root).status == "fail"


def test_incomplete_table_is_unknown(tmp_path: Path) -> None:
    contract, root, _ = _setup(
        tmp_path, _artifact(unknown=["N1: fewer than two connector test points"], verdict="fail")
    )
    check = _check(_bind(contract), root)
    assert check.status == "unknown"
    assert "fewer than two" in check.detail


def test_changed_artifact_fails(tmp_path: Path) -> None:
    contract, root, path = _setup(tmp_path, _artifact())
    path.write_text(json.dumps(_artifact(groups=[])) + "\n", encoding="utf-8")
    check = _check(_bind(contract), root)
    assert check.status == "fail"
    assert "changed since import" in check.detail


def test_missing_artifact_is_unknown(tmp_path: Path) -> None:
    contract, root, path = _setup(tmp_path, _artifact())
    path.unlink()
    assert _check(_bind(contract), root).status == "unknown"


@pytest.mark.parametrize(
    "changes",
    [
        {"verdict": "fail"},
        {"unknown": ["wires"]},
        {"groups": []},
        {"artifact_kind": "wire_crimp"},
        {"extra": True},
    ],
)
def test_malformed_artifact_is_refused(changes: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="malformed wire-continuity"):
        extract_import("wire-continuity", _artifact(**changes))


def test_duplicate_point_is_refused() -> None:
    groups = _artifact()["groups"]
    groups[1]["points"] = [groups[0]["points"][0], *groups[1]["points"][1:]]
    with pytest.raises(ValueError, match="more than one group"):
        extract_import("wire-continuity", _artifact(groups=groups))


def test_continuity_requires_an_attribute_characteristic() -> None:
    contract = load_contract(EXAMPLE / "smart-kettle.prodeng.json")
    data = contract.model_dump(mode="json")
    variable = next(c for c in data["characteristics"] if c["kind"] == "variable")
    variable["continuity"] = True
    with pytest.raises(ValidationError, match="continuity requires an attribute"):
        ProdengContract.model_validate(data)
