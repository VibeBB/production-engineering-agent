from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from prodeng.contract import ProdengContract, load_contract
from prodeng.gates import GateCheck, run_gates
from prodeng.imports import MechAppearanceSource, extract_import, import_source
from prodeng.projections import write_projections

EXAMPLE = Path(__file__).parents[1] / "examples" / "smart-kettle"
FIXTURE = (
    Path(__file__).parent / "fixtures" / "upstream" / "smart-kettle-shell.mech-appearance.json"
)
PAIRS = {
    "smart-kettle-shell:top:scratch": ["LS1", "LS2"],
    "smart-kettle-shell:top:color_deviation": ["LS3", "LS4"],
    "smart-kettle-shell:front:layer_line": ["LS10", "LS9"],
}
ALL = ["LS1", "LS10", "LS2", "LS3", "LS4", "LS9"]


def _artifact() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _workspace(tmp_path: Path, artifact: dict[str, Any]) -> tuple[Path, Path]:
    shutil.copytree(EXAMPLE, tmp_path / "smart-kettle")
    path = tmp_path / "mech" / "out" / "smart-kettle-shell.mech-appearance.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    return tmp_path / "smart-kettle" / "smart-kettle.prodeng.json", path


def _bound(
    contract: ProdengContract, holders: dict[str, list[str]], kind: str = "attribute"
) -> ProdengContract:
    data = contract.model_dump(mode="json")
    cosmetic: dict[str, Any] = {
        "id": "CH-06",
        "description": "Housing cosmetic appearance",
        "classification": "major",
        "kind": kind,
        "criterion": "No defect beyond the accept limit sample",
        "sources": ["import:mech"],
    }
    if kind == "variable":
        cosmetic.update(unit="mm", usl=0.3)
    data["characteristics"].append(cosmetic)
    for index, (inspection_id, samples) in enumerate(sorted(holders.items())):
        data["inspections"].append(
            {
                "id": inspection_id,
                "characteristic": "CH-06",
                "operation": "OP04" if index == 0 else "OP06",
                "method": "visual",
                "sampling": {"mode": "full"},
                "equipment": "D65 booth at 1000 lx",
                "reaction_plan": "Quarantine and compare with the limit samples",
                "limit_samples": samples,
            }
        )
    return ProdengContract.model_validate(data)


def _imported(
    tmp_path: Path, artifact: dict[str, Any] | None = None
) -> tuple[ProdengContract, Path, Path]:
    contract_path, artifact_path = _workspace(tmp_path, artifact or _artifact())
    contract = import_source(
        load_contract(contract_path), "mech-appearance", artifact_path, contract_path.parent
    )
    return contract, contract_path.parent, artifact_path


def _checks(contract: ProdengContract, contract_dir: Path) -> dict[str, GateCheck]:
    return {
        check.subject: check
        for check in run_gates(contract, contract_dir).checks
        if check.id == "appearance.limit_samples"
    }


def test_real_mech_export_extracts_its_limit_samples() -> None:
    data = extract_import("mech-appearance", _artifact())
    assert data.limit_samples == ["LS1", "LS2", "LS3", "LS4", "LS9", "LS10"]


def test_unbound_limit_samples_fail_and_class_c_needs_none(tmp_path: Path) -> None:
    contract, contract_dir, _ = _imported(tmp_path)
    checks = _checks(contract, contract_dir)
    assert set(checks) == set(PAIRS)
    assert {check.status for check in checks.values()} == {"fail"}
    assert "no visual inspection holds LS1 (accept) / LS2 (reject)" in (
        checks["smart-kettle-shell:top:scratch"].detail
    )
    assert run_gates(contract, contract_dir).verdict == "fail"


def test_every_pair_held_by_a_visual_attribute_inspection_passes(tmp_path: Path) -> None:
    contract, contract_dir, _ = _imported(tmp_path)
    checks = _checks(_bound(contract, {"IN-06": ALL}), contract_dir)
    assert {check.status for check in checks.values()} == {"pass"}
    scratch = checks["smart-kettle-shell:top:scratch"]
    assert scratch.measured == "IN-06"
    assert scratch.limit == "size <= 0.3 mm, count <= 1"
    assert "class A; LS1 (accept) / LS2 (reject)" in scratch.detail
    assert "450 mm, 1000 lx, 10 s, 45 deg (customer cosmetic spec CS-12 rev B)" in scratch.detail
    assert checks["smart-kettle-shell:top:color_deviation"].limit == "delta <= 1.5, count <= 0"


def test_pairs_may_be_split_but_not_halved(tmp_path: Path) -> None:
    contract, contract_dir, _ = _imported(tmp_path)
    split = _bound(contract, {"IN-06": ["LS1", "LS2", "LS3", "LS4"], "IN-07": ["LS10", "LS9"]})
    checks = _checks(split, contract_dir)
    assert {check.status for check in checks.values()} == {"pass"}
    assert checks["smart-kettle-shell:front:layer_line"].measured == "IN-07"
    halved = _bound(contract, {"IN-06": ["LS1", "LS3", "LS4", "LS9", "LS10"], "IN-07": ["LS2"]})
    checks = _checks(halved, contract_dir)
    assert checks["smart-kettle-shell:top:scratch"].status == "fail"
    assert checks["smart-kettle-shell:top:color_deviation"].status == "pass"


def test_limit_samples_need_an_attribute_characteristic(tmp_path: Path) -> None:
    contract, contract_dir, _ = _imported(tmp_path)
    checks = _checks(_bound(contract, {"IN-06": ALL}, kind="variable"), contract_dir)
    assert {check.status for check in checks.values()} == {"fail"}
    assert "variable characteristic" in checks["smart-kettle-shell:top:scratch"].detail


def test_changed_or_missing_artifact(tmp_path: Path) -> None:
    contract, contract_dir, artifact_path = _imported(tmp_path)
    contract = _bound(contract, {"IN-06": ALL})
    changed = _artifact()
    changed["viewing"]["illuminance_lux"] = 500
    artifact_path.write_text(json.dumps(changed), encoding="utf-8")
    checks = list(_checks(contract, contract_dir).values())
    assert [(c.status, c.detail) for c in checks] == [("fail", "artifact changed since import")]
    artifact_path.unlink()
    checks = list(_checks(contract, contract_dir).values())
    assert [c.status for c in checks] == ["unknown"]
    assert checks[0].detail.startswith("artifact unreadable")


def test_class_c_only_artifact_passes_without_inspections(tmp_path: Path) -> None:
    artifact = _artifact()
    artifact["surfaces"] = [s for s in artifact["surfaces"] if s["cosmetic_class"] == "C"]
    artifact["samples"] = []
    contract, contract_dir, _ = _imported(tmp_path, artifact)
    checks = list(_checks(contract, contract_dir).values())
    assert [(c.status, c.detail) for c in checks] == [
        ("pass", "class C only; no limit samples required")
    ]


def test_class_a_limit_without_a_sample_pair_fails(tmp_path: Path) -> None:
    artifact = _artifact()
    artifact["samples"] = [s for s in artifact["samples"] if s["id"] != "LS2"]
    contract, contract_dir, _ = _imported(tmp_path, artifact)
    held = [sample for sample in ALL if sample != "LS2"]
    checks = _checks(_bound(contract, {"IN-06": held}), contract_dir)
    scratch = checks["smart-kettle-shell:top:scratch"]
    assert scratch.status == "fail"
    assert "lacks an accept/reject sample pair (has ['accept'])" in scratch.detail
    assert checks["smart-kettle-shell:top:color_deviation"].status == "pass"


def _malformed(kind: str) -> dict[str, Any]:
    data = _artifact()
    if kind == "extra_key":
        data["owner"] = "mech"
    elif kind == "wrong_kind":
        data["artifact_kind"] = "mech_envelope"
    elif kind == "bad_class":
        data["surfaces"][0]["cosmetic_class"] = "D"
    elif kind == "duplicate_face":
        data["surfaces"][0]["face"] = "top"
    elif kind == "duplicate_sample":
        data["samples"][1]["id"] = "LS1"
    elif kind == "undeclared_sample":
        data["samples"][0]["defect"] = "dent"
    elif kind == "delta_with_size":
        data["surfaces"][2]["defects"][0]["max_size_mm"] = 1.0
    elif kind == "size_without_bound":
        data["surfaces"][2]["defects"][1]["max_size_mm"] = None
    elif kind == "angle":
        data["viewing"]["angle_deg"] = 120
    elif kind == "no_surfaces":
        data["surfaces"] = []
        data["samples"] = []
    elif kind == "bad_sha":
        data["brief_sha256"] = "0" * 63
    elif kind == "bad_side":
        data["samples"][0]["side"] = "borderline"
    return data


MALFORMED = [
    "extra_key",
    "wrong_kind",
    "bad_class",
    "duplicate_face",
    "duplicate_sample",
    "undeclared_sample",
    "delta_with_size",
    "size_without_bound",
    "angle",
    "no_surfaces",
    "bad_sha",
    "bad_side",
]


@pytest.mark.parametrize("kind", MALFORMED)
def test_malformed_artifacts_are_rejected(tmp_path: Path, kind: str) -> None:
    data = _malformed(kind)
    with pytest.raises(ValidationError):
        MechAppearanceSource.model_validate(data)
    contract_path, artifact_path = _workspace(tmp_path, data)
    with pytest.raises(ValueError, match="malformed mech-appearance artifact"):
        import_source(
            load_contract(contract_path), "mech-appearance", artifact_path, contract_path.parent
        )


def test_contract_rejects_bad_limit_sample_references(tmp_path: Path) -> None:
    contract, _, _ = _imported(tmp_path)
    with pytest.raises(ValidationError, match="which no mech-appearance import provides"):
        _bound(contract, {"IN-06": ["LS1", "LS99"]})
    with pytest.raises(ValidationError, match="lists a limit sample twice"):
        _bound(contract, {"IN-06": ["LS1", "LS1"]})
    data = contract.model_dump(mode="json")
    data["inspections"][0]["limit_samples"] = ["LS1"]
    with pytest.raises(ValidationError, match="IN-01 holds limit samples but is not visual"):
        ProdengContract.model_validate(data)


def test_one_limit_sample_from_one_import(tmp_path: Path) -> None:
    contract, contract_dir, artifact_path = _imported(tmp_path)
    copy = artifact_path.with_name("lid.mech-appearance.json")
    shutil.copy(artifact_path, copy)
    with pytest.raises(ValidationError, match="more than one mech-appearance import"):
        import_source(contract, "mech-appearance", copy, contract_dir)


def test_projections_carry_the_limit_samples(tmp_path: Path) -> None:
    contract, _, _ = _imported(tmp_path)
    contract = _bound(contract, {"IN-06": ALL})
    out = tmp_path / "out"
    write_projections(contract, "smart-kettle", out)
    plan = json.loads((out / "inspection-plan.json").read_text(encoding="utf-8"))
    held = {row["inspection_id"]: row["limit_samples"] for row in plan}
    assert held["IN-06"] == ALL
    assert held["IN-01"] == []
    instructions = (out / "work-instructions.md").read_text(encoding="utf-8")
    assert "IN-06 (visual, CH-06; limit samples LS1, LS10, LS2, LS3, LS4, LS9)" in instructions
