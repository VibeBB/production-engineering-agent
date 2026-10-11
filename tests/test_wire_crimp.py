from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from prodeng.contract import Characteristic, ProdengContract, load_contract
from prodeng.gates import GateCheck, run_gates
from prodeng.imports import extract_import, import_source

EXAMPLE = Path(__file__).parents[1] / "examples" / "smart-kettle"
FIXTURE = Path(__file__).parent / "fixtures" / "upstream" / "sensor-harness.wire-crimp.json"
HEIGHT = {"CC1": (0.87, 0.93), "CC2": (0.82, 0.88)}
PULL = {"CC1": 30.0, "CC2": 20.0}


def _artifact(**changes: Any) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data.update(changes)
    return data


def _char(cid: str, condition: str, quantity: str, lsl: float, usl: float | None) -> dict[str, Any]:
    return {
        "id": cid,
        "description": f"{condition} {quantity}",
        "classification": "critical",
        "kind": "variable",
        "unit": "mm" if quantity == "crimp_height" else "N",
        "lsl": lsl,
        "usl": usl,
        "sources": ["R001"],
        "crimp": {"condition": condition, "quantity": quantity},
    }


def _bind(
    contract: ProdengContract,
    *,
    height: dict[str, tuple[float, float]] | None = None,
    pull: dict[str, float] | None = None,
    op_kind: str = "harness",
) -> ProdengContract:
    data = contract.model_dump(mode="json")
    data["operations"].append(
        {"id": "OP07", "name": "Crimp harness", "kind": op_kind, "station": "ST7", "operators": 1}
    )
    number = 90
    for condition, (lsl, usl) in (HEIGHT if height is None else height).items():
        data["characteristics"].append(_char(f"CH-{number}", condition, "crimp_height", lsl, usl))
        number += 1
    for condition, lsl in (PULL if pull is None else pull).items():
        data["characteristics"].append(_char(f"CH-{number}", condition, "pull_force", lsl, None))
        number += 1
    for item in data["characteristics"]:
        if item.get("crimp"):
            data["inspections"].append(
                {
                    "id": f"IN-{item['id'][3:]}",
                    "characteristic": item["id"],
                    "operation": "OP07",
                    "method": "measurement",
                    "sampling": {"mode": "full"},
                    "equipment": "crimp height micrometer / pull tester",
                    "reaction_plan": "Stop the applicator, quarantine the lot and re-set up.",
                }
            )
    return ProdengContract.model_validate(data)


def _imported(tmp_path: Path, artifact: dict[str, Any]) -> tuple[ProdengContract, Path, Path]:
    shutil.copytree(EXAMPLE, tmp_path / "smart-kettle")
    contract_path = tmp_path / "smart-kettle" / "smart-kettle.prodeng.json"
    path = contract_path.parent / "upstream" / "sensor-harness.wire-crimp.json"
    path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    contract = import_source(load_contract(contract_path), "wire-crimp", path, contract_path.parent)
    return contract, contract_path.parent, path


def _checks(contract: ProdengContract, contract_dir: Path) -> dict[str, GateCheck]:
    return {c.subject: c for c in run_gates(contract, contract_dir).checks if c.id == "wire.crimp"}


def test_real_wire_agent_export_imports() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert extract_import("wire-crimp", payload).parts == []


def test_bound_conditions_pass(tmp_path: Path) -> None:
    contract, contract_dir, _ = _imported(tmp_path, _artifact())
    checks = _checks(_bind(contract), contract_dir)
    assert set(checks) == {f"CC{n}:{q}" for n in (1, 2) for q in ("crimp_height", "pull_force")}
    assert all(c.status == "pass" for c in checks.values()), checks
    assert checks["CC1:crimp_height"].detail == "CH-90 by IN-90"
    assert checks["CC1:crimp_height"].measured == 4


def test_unbound_condition_fails(tmp_path: Path) -> None:
    contract, contract_dir, _ = _imported(tmp_path, _artifact())
    checks = _checks(_bind(contract, pull={"CC1": 30.0}), contract_dir)
    assert checks["CC2:pull_force"].status == "fail"
    assert checks["CC2:pull_force"].detail == "no characteristic controls pull_force"


@pytest.mark.parametrize(
    ("height", "pull", "subject"),
    [
        ({"CC1": (0.869, 0.93), "CC2": HEIGHT["CC2"]}, PULL, "CC1:crimp_height"),
        ({"CC1": (0.87, 0.931), "CC2": HEIGHT["CC2"]}, PULL, "CC1:crimp_height"),
        (HEIGHT, {"CC1": 29.9, "CC2": 20.0}, "CC1:pull_force"),
    ],
)
def test_limits_looser_than_the_table_fail(
    tmp_path: Path, height: dict[str, tuple[float, float]], pull: dict[str, float], subject: str
) -> None:
    contract, contract_dir, _ = _imported(tmp_path, _artifact())
    assert _checks(_bind(contract, height=height, pull=pull), contract_dir)[subject].status == (
        "fail"
    )


def test_tighter_limits_pass(tmp_path: Path) -> None:
    contract, contract_dir, _ = _imported(tmp_path, _artifact())
    height = {"CC1": (0.88, 0.92), "CC2": (0.83, 0.87)}
    checks = _checks(_bind(contract, height=height, pull={"CC1": 35, "CC2": 25}), contract_dir)
    assert all(c.status == "pass" for c in checks.values())


def test_inspection_off_harness_operation_fails(tmp_path: Path) -> None:
    contract, contract_dir, _ = _imported(tmp_path, _artifact())
    check = _checks(_bind(contract, op_kind="test"), contract_dir)["CC1:pull_force"]
    assert check.status == "fail" and "not inspected on a harness operation" in check.detail


def test_binding_to_unknown_condition_fails(tmp_path: Path) -> None:
    contract, contract_dir, _ = _imported(tmp_path, _artifact())
    bound = _bind(contract, height={**HEIGHT, "CC9": (0.8, 0.9)})
    assert _checks(bound, contract_dir)["CH-92"].detail == "CC9 is not in WH-0001"


def test_incomplete_table_is_unknown(tmp_path: Path) -> None:
    contract, contract_dir, path = _imported(tmp_path, _artifact(verdict="fail", unknown=["W3:a"]))
    assert (
        _checks(_bind(contract), contract_dir)[str(path.relative_to(contract_dir))].status
        == "unknown"
    )


def test_changed_artifact_fails(tmp_path: Path) -> None:
    contract, contract_dir, path = _imported(tmp_path, _artifact())
    path.write_text(json.dumps(_artifact(contract_id="WH-0002")), encoding="utf-8")
    check = _checks(_bind(contract), contract_dir)[str(path.relative_to(contract_dir))]
    assert check.status == "fail" and check.detail == "artifact changed since import"


def test_missing_artifact_is_unknown(tmp_path: Path) -> None:
    contract, contract_dir, path = _imported(tmp_path, _artifact())
    path.unlink()
    assert _checks(contract, contract_dir)[str(path.relative_to(contract_dir))].status == "unknown"


@pytest.mark.parametrize(
    "changes",
    [
        {"verdict": "pass", "unknown": ["W1:a"]},
        {"artifact_kind": "wire_contract"},
        {"extra": 1},
    ],
)
def test_malformed_artifact_is_rejected(changes: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="malformed wire-crimp"):
        extract_import("wire-crimp", _artifact(**changes))


@pytest.mark.parametrize(("kind", "unit"), [("variable", "N"), ("attribute", None)])
def test_crimp_binding_needs_matching_unit(kind: str, unit: str | None) -> None:
    data = _char("CH-90", "CC1", "crimp_height", 0.87, 0.93) | {"kind": kind, "unit": unit}
    if kind == "attribute":
        data["criterion"] = "visual"
    with pytest.raises(ValidationError):
        Characteristic.model_validate(data)
