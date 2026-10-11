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
FIXTURE = Path(__file__).parent / "fixtures" / "upstream" / "enclosure.brief.json"

# enclosure.brief.json is 80 x 60 x 30 mm; 2 x 2 x 1 units with 10 mm cushion
# need exactly 180 x 140 x 50 mm. Gross 4 x 0.5 + 0.3 = 2.3 kg; four cartons
# above the bottom one at safety 3 load it with 4 x 2.3 x 9.80665 x 3 N.
PACKAGING: dict[str, Any] = {
    "carton_inner_mm": [180, 140, 50],
    "arrangement": [2, 2, 1],
    "cushion_mm": 10,
    "unit_mass_kg": 0.5,
    "packaging_mass_kg": 0.3,
    "max_gross_kg": 2.3,
    "source": "ISO 11228-1 one-hand carry limit",
    "pallet": {
        "layers": 5,
        "box_compression_n": 270.66354,
        "safety_factor": 3,
        "source": "carton supplier BCT sheet",
    },
}


def _contract(tmp_path: Path, brief: bool = True, **changes: Any) -> tuple[ProdengContract, Path]:
    shutil.copytree(EXAMPLE, tmp_path / "smart-kettle")
    root = tmp_path / "smart-kettle"
    data = json.loads((root / "smart-kettle.prodeng.json").read_text(encoding="utf-8"))
    data["packaging"] = {**PACKAGING, **changes}
    contract = ProdengContract.model_validate(data)
    if brief:
        path = root / "upstream" / "enclosure.brief.json"
        shutil.copyfile(FIXTURE, path)
        contract = import_source(contract, "mech-brief", path, root)
    return contract, root


def _checks(contract: ProdengContract, root: Path) -> dict[str, GateCheck]:
    return {c.id: c for c in run_gates(contract, root).checks if c.id.startswith("packaging.")}


def test_boundaries_pass(tmp_path: Path) -> None:
    checks = _checks(*_contract(tmp_path))
    assert {k: c.status for k, c in checks.items()} == {
        "packaging.fit": "pass",
        "packaging.mass": "pass",
        "packaging.stack": "pass",
        "packaging.operation": "pass",
    }
    assert checks["packaging.fit"].measured == 0
    assert checks["packaging.stack"].measured == pytest.approx(270.66354)


@pytest.mark.parametrize(
    ("changes", "gate"),
    [
        ({"carton_inner_mm": [180, 139.9, 50]}, "packaging.fit"),
        ({"cushion_mm": 10.1}, "packaging.fit"),
        ({"max_gross_kg": 2.29}, "packaging.mass"),
        ({"pallet": {**PACKAGING["pallet"], "box_compression_n": 270.66}}, "packaging.stack"),
        ({"pallet": {**PACKAGING["pallet"], "layers": 6}}, "packaging.stack"),
    ],
)
def test_just_past_boundary_fails(tmp_path: Path, changes: dict[str, Any], gate: str) -> None:
    checks = _checks(*_contract(tmp_path, **changes))
    assert checks[gate].status == "fail"


def test_single_layer_and_no_pallet(tmp_path: Path) -> None:
    pallet = {**PACKAGING["pallet"], "layers": 1}
    assert _checks(*_contract(tmp_path / "a", pallet=pallet))["packaging.stack"].measured == 0
    assert "packaging.stack" not in _checks(*_contract(tmp_path / "b", pallet=None))


def test_undeclared_packaging_emits_no_gate(tmp_path: Path) -> None:
    contract = load_contract(EXAMPLE / "smart-kettle.prodeng.json")
    assert not _checks(contract, EXAMPLE)


def test_missing_envelope_is_unknown(tmp_path: Path) -> None:
    assert _checks(*_contract(tmp_path, brief=False))["packaging.fit"].status == "unknown"


def test_changed_missing_and_ambiguous_briefs(tmp_path: Path) -> None:
    contract, root = _contract(tmp_path)
    path = root / "upstream" / "enclosure.brief.json"
    path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    assert _checks(contract, root)["packaging.fit"].status == "fail"
    path.unlink()
    assert _checks(contract, root)["packaging.fit"].status == "unknown"
    shutil.copyfile(FIXTURE, path)
    other = root / "upstream" / "other.brief.json"
    shutil.copyfile(FIXTURE, other)
    contract = import_source(contract, "mech-brief", other, root)
    assert _checks(contract, root)["packaging.fit"].status == "fail"


def test_no_packing_operation_fails(tmp_path: Path) -> None:
    contract, root = _contract(tmp_path)
    data = contract.model_dump(mode="json")
    data["operations"] = [op for op in data["operations"] if op["kind"] != "packing"]
    data["inspections"] = [
        item
        for item in data["inspections"]
        if item["operation"] in {op["id"] for op in data["operations"]}
    ]
    checks = _checks(ProdengContract.model_validate(data), root)
    assert checks["packaging.operation"].status == "fail"


@pytest.mark.parametrize(
    "enclosure",
    [None, {"width_mm": 80, "depth_mm": 60}, {"width_mm": 0, "depth_mm": 60, "height_mm": 30}],
)
def test_brief_without_envelope_is_rejected(enclosure: object) -> None:
    with pytest.raises(ValueError, match="mech brief"):
        extract_import("mech-brief", {"name": "demo", "enclosure": enclosure})


@pytest.mark.parametrize(
    "changes",
    [
        {"carton_inner_mm": [180, 0, 50]},
        {"arrangement": [2, 0, 1]},
        {"cushion_mm": -1},
        {"unit_mass_kg": 0},
        {"source": ""},
        {"pallet": {**PACKAGING["pallet"], "safety_factor": 0.9}},
    ],
)
def test_invalid_packaging_is_rejected(changes: dict[str, Any]) -> None:
    data = json.loads((EXAMPLE / "smart-kettle.prodeng.json").read_text(encoding="utf-8"))
    data["packaging"] = {**PACKAGING, **changes}
    with pytest.raises(ValidationError):
        ProdengContract.model_validate(data)


IN_BOX = [
    {"id": "guide", "name": "Quick start", "kind": "document", "first_used_state": "idle"},
    {"id": "kettle", "name": "Kettle", "kind": "product"},
    {"id": "base", "name": "Power base", "kind": "accessory"},
]
CONTENTS = [
    {"id": "guide", "layer": 1, "operation": "OP06"},
    {"id": "kettle", "layer": 2, "operation": "OP06"},
    {"id": "base", "layer": 2, "operation": "OP06"},
]


def _with_ux(
    tmp_path: Path, in_box: list[dict[str, Any]] | None = IN_BOX, **changes: Any
) -> tuple[ProdengContract, Path]:
    contract, root = _contract(tmp_path, **changes)
    path = root / "upstream" / "kettle.ux.json"
    ux: dict[str, Any] = {"system": "ux", "product": {"surfaces": []}}
    if in_box is not None:
        ux["oobe"] = {"in_box": in_box}
    path.write_text(json.dumps(ux), encoding="utf-8")
    return import_source(contract, "ux-contract", path, root), root


def _oobe(contract: ProdengContract, root: Path) -> GateCheck:
    return _checks(contract, root)["packaging.oobe"]


def test_oobe_contents_in_unboxing_order_pass(tmp_path: Path) -> None:
    check = _oobe(*_with_ux(tmp_path, contents=CONTENTS))
    assert check.status == "pass"
    assert check.detail == "3 items packed in unboxing order"


@pytest.mark.parametrize(
    ("contents", "detail"),
    [
        (CONTENTS[:2], "base not packed"),
        ([*CONTENTS, {"id": "spare", "layer": 3, "operation": "OP06"}], "spare not in the UX box"),
        (
            [{**CONTENTS[0], "layer": 3}, *CONTENTS[1:]],
            "kettle (layer 2) above guide (layer 3)",
        ),
        (
            [{**CONTENTS[0], "operation": "OP01"}, *CONTENTS[1:]],
            "guide: OP01 is not a packing operation",
        ),
    ],
    ids=["missing", "extra", "order", "operation"],
)
def test_oobe_contents_mismatch_fails(
    tmp_path: Path, contents: list[dict[str, Any]], detail: str
) -> None:
    check = _oobe(*_with_ux(tmp_path, contents=contents))
    assert check.status == "fail"
    assert check.detail == detail


def test_oobe_without_contents_or_ux_list(tmp_path: Path) -> None:
    assert _oobe(*_with_ux(tmp_path)).detail == "packaging.contents missing"
    assert _oobe(*_with_ux(tmp_path / "b", in_box=None, contents=CONTENTS)).status == "unknown"
    contract, root = _contract(tmp_path / "c", contents=CONTENTS)
    assert _oobe(contract, root).status == "unknown"
    contract, root = _contract(tmp_path / "d")
    assert "packaging.oobe" not in _checks(contract, root)


def test_oobe_stale_ambiguous_and_malformed_ux(tmp_path: Path) -> None:
    contract, root = _with_ux(tmp_path, contents=CONTENTS)
    path = root / "upstream" / "kettle.ux.json"
    path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    assert _oobe(contract, root).status == "fail"
    malformed, root2 = _with_ux(tmp_path / "m", in_box=[{"name": "no id"}], contents=CONTENTS)
    assert _oobe(malformed, root2).detail == "malformed oobe.in_box"
    other = root2 / "upstream" / "other.ux.json"
    shutil.copyfile(root2 / "upstream" / "kettle.ux.json", other)
    ambiguous = import_source(malformed, "ux-contract", other, root2)
    assert _oobe(ambiguous, root2).status == "fail"


def test_duplicate_contents_rejected() -> None:
    with pytest.raises(ValidationError):
        ProdengContract.model_validate(
            {
                **json.loads((EXAMPLE / "smart-kettle.prodeng.json").read_text(encoding="utf-8")),
                "packaging": {**PACKAGING, "contents": [CONTENTS[0], CONTENTS[0]]},
            }
        )
