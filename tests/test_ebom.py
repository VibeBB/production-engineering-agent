"""ebom.complete and ebom.json: one unit's parts from the pinned circuit, mech and wire sources."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from prodeng.contract import ProdengContract, load_contract
from prodeng.ebom import product_ebom
from prodeng.gates import GateCheck, run_gates
from prodeng.imports import ImportKind, import_source
from prodeng.projections import write_projections

EXAMPLE = Path(__file__).parents[1] / "examples" / "smart-kettle"
FIXTURES = Path(__file__).parent / "fixtures" / "upstream"
ALL = ["circuit-brief", "mech-brief", "wire-contract"]


def _setup(tmp_path: Path, sources: list[str]) -> tuple[ProdengContract, Path]:
    shutil.copytree(EXAMPLE, tmp_path / "smart-kettle")
    root = tmp_path / "smart-kettle"
    upstream = root / "upstream"
    contract = load_contract(root / "smart-kettle.prodeng.json")
    sources_to_pin: tuple[tuple[ImportKind, str], ...] = (
        ("mech-brief", "enclosure.brief.json"),
        ("wire-contract", "sensor-harness.contract.json"),
    )
    for kind, name in sources_to_pin:
        shutil.copy(FIXTURES / name, upstream / name)
        contract = import_source(contract, kind, upstream / name, root)
    data = contract.model_dump(mode="json") | {"ebom_sources": sources}
    return ProdengContract.model_validate(data), root


def _check(contract: ProdengContract, root: Path) -> GateCheck:
    checks = [c for c in run_gates(contract, root).checks if c.id == "ebom.complete"]
    assert len(checks) == 1
    return checks[0]


def _lines(ebom: dict[str, Any], system: str) -> dict[str, dict[str, Any]]:
    return {line["item"]: line for line in ebom["lines"] if line["system"] == system}


def test_three_sources_merge_into_one_unit(tmp_path: Path) -> None:
    contract, root = _setup(tmp_path, ALL)
    ebom: dict[str, Any] = product_ebom(contract, root)
    assert ebom["verdict"] == "pass", (ebom["failed"], ebom["unknown"])
    assert [s["kind"] for s in ebom["sources"]] == ALL
    brief = json.loads((root / "upstream/smart-kettle.circuit-brief.json").read_text("utf-8"))
    circuit = _lines(ebom, "circuit")
    assert sum(
        line["quantity"] for line in circuit.values() if not line["item"].startswith("pcb:")
    ) == len(brief["parts"])
    assert any(item.startswith("pcb:") for item in circuit)
    harness = json.loads((FIXTURES / "sensor-harness.contract.json").read_text("utf-8"))
    wire = _lines(ebom, "wire")
    for wire_type in harness["wire_types"]:
        total = sum(w["length_m"] for w in harness["wires"] if w["wire_type"] == wire_type["id"])
        assert wire[wire_type["id"]]["quantity"] == pytest.approx(total)
    housings = sum(
        line["quantity"] for line in wire.values() if line["description"] == "connector housing"
    )
    assert housings == len(harness["connectors"])
    mech = _lines(ebom, "mech")
    assert any(item.endswith("-base") for item in mech)
    assert any(item.endswith("-lid") for item in mech)
    check = _check(contract, root)
    assert check.status == "pass"
    assert check.measured == len(ebom["lines"])


def test_declared_source_not_imported_is_unknown(tmp_path: Path) -> None:
    contract, root = _setup(tmp_path, ALL)
    data = contract.model_dump(mode="json")
    data["imports"] = [i for i in data["imports"] if i["kind"] != "wire-contract"]
    check = _check(ProdengContract.model_validate(data), root)
    assert check.status == "unknown"
    assert "wire-contract: not imported" in check.detail


def test_changed_source_fails(tmp_path: Path) -> None:
    contract, root = _setup(tmp_path, ALL)
    path = root / "upstream" / "sensor-harness.contract.json"
    path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    check = _check(contract, root)
    assert check.status == "fail"
    assert "changed since import" in check.detail


def test_missing_source_file_is_unknown(tmp_path: Path) -> None:
    contract, root = _setup(tmp_path, ALL)
    (root / "upstream" / "enclosure.brief.json").unlink()
    assert _check(contract, root).status == "unknown"


def test_malformed_source_fails(tmp_path: Path) -> None:
    contract, root = _setup(tmp_path, ["wire-contract"])
    data = contract.model_dump(mode="json")
    path = root / "upstream" / "bad.contract.json"
    payload = json.loads((FIXTURES / "sensor-harness.contract.json").read_text("utf-8"))
    payload["wires"][0]["wire_type"] = "WT99"
    path.write_text(json.dumps(payload), encoding="utf-8")
    data["imports"] = [i for i in data["imports"] if i["kind"] != "wire-contract"]
    contract = import_source(ProdengContract.model_validate(data), "wire-contract", path, root)
    check = _check(contract, root)
    assert check.status == "fail"
    assert "undeclared wire types: WT99" in check.detail


def test_no_declared_sources_runs_no_gate(tmp_path: Path) -> None:
    contract, root = _setup(tmp_path, [])
    assert not [c for c in run_gates(contract, root).checks if c.id == "ebom.complete"]


def test_duplicate_sources_are_refused(tmp_path: Path) -> None:
    contract, _ = _setup(tmp_path, [])
    data = contract.model_dump(mode="json") | {"ebom_sources": ["mech-brief", "mech-brief"]}
    with pytest.raises(ValidationError, match="duplicate ebom_sources"):
        ProdengContract.model_validate(data)


def test_projection_writes_ebom_json(tmp_path: Path) -> None:
    contract, root = _setup(tmp_path, ALL)
    paths = write_projections(contract, "smart-kettle", tmp_path / "out", root)
    written = json.loads(paths["ebom"].read_text(encoding="utf-8"))
    assert written == json.loads(json.dumps(product_ebom(contract, root)))
    assert "ebom" not in write_projections(contract, "smart-kettle", tmp_path / "out2")
