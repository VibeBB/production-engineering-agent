from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from prodeng.contract import ProdengContract, load_contract
from prodeng.gates import GateCheck, run_gates
from prodeng.imports import FpgaProductionSource, extract_import, import_source

EXAMPLE = Path(__file__).parents[1] / "examples" / "smart-kettle"
FIXTURE = Path(__file__).parent / "fixtures" / "upstream" / "blinky.fpga-production.json"
BITSTREAM = b"\xff\x00gated bitstream" * 32


def _artifact(**changes: Any) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data.update(
        target="flash",
        argv=["openFPGALoader", "-b", "ulx3s", "-f", data["bitstream"]],
        bitstream_sha256=hashlib.sha256(BITSTREAM).hexdigest(),
        bitstream_bytes=len(BITSTREAM),
    )
    data.update(changes)
    return data


def _workspace(tmp_path: Path, artifact: dict[str, Any]) -> tuple[Path, Path]:
    shutil.copytree(EXAMPLE, tmp_path / "smart-kettle")
    reports = tmp_path / "fpga" / "fpga-reports"
    reports.mkdir(parents=True)
    (tmp_path / "fpga" / "build").mkdir()
    (tmp_path / "fpga" / "build" / "blinky.bit").write_bytes(BITSTREAM)
    path = reports / "blinky.fpga-production.json"
    path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    return tmp_path / "smart-kettle" / "smart-kettle.prodeng.json", path


def _bound(contract: ProdengContract, programs: list[str]) -> ProdengContract:
    data = contract.model_dump(mode="json")
    for operation in data["operations"]:
        if operation["id"] == "OP03":
            operation["programs"] = programs
    return ProdengContract.model_validate(data)


def _imported(tmp_path: Path, artifact: dict[str, Any]) -> tuple[ProdengContract, Path, Path]:
    contract_path, artifact_path = _workspace(tmp_path, artifact)
    contract = import_source(
        load_contract(contract_path), "fpga-production", artifact_path, contract_path.parent
    )
    return _bound(contract, ["U1"]), contract_path.parent, artifact_path


def _gate(contract: ProdengContract, contract_dir: Path) -> GateCheck:
    found = [c for c in run_gates(contract, contract_dir).checks if c.id == "fpga.programming"]
    assert len(found) == 1
    return found[0]


def test_real_fpga_agent_export_imports() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert extract_import("fpga-production", payload).parts == ["U1"]


def test_gated_flash_bitstream_passes(tmp_path: Path) -> None:
    contract, contract_dir, _ = _imported(tmp_path, _artifact())
    imported = [item for item in contract.imports if item.kind == "fpga-production"]
    assert imported[0].system == "fpga" and imported[0].extracted.parts == ["U1"]
    check = _gate(contract, contract_dir)
    assert check.status == "pass", check
    assert check.measured == check.limit == hashlib.sha256(BITSTREAM).hexdigest()
    assert "OP03" in check.detail and "openFPGALoader -b ulx3s -f" in check.detail
    assert run_gates(contract, contract_dir).verdict == "pass"


def test_unbound_device_fails(tmp_path: Path) -> None:
    contract, contract_dir, _ = _imported(tmp_path, _artifact())
    check = _gate(_bound(contract, []), contract_dir)
    assert check.status == "fail" and "no programming operation" in check.detail


def test_sram_target_fails(tmp_path: Path) -> None:
    artifact = _artifact(
        target="sram", argv=["openFPGALoader", "-b", "ulx3s", "../build/blinky.bit"]
    )
    contract, contract_dir, _ = _imported(tmp_path, artifact)
    check = _gate(contract, contract_dir)
    assert check.status == "fail" and check.measured == "sram" and check.limit == "flash"


def test_tampered_bitstream_fails_and_missing_is_unknown(tmp_path: Path) -> None:
    contract, contract_dir, artifact_path = _imported(tmp_path, _artifact())
    bitstream = artifact_path.parent.parent / "build" / "blinky.bit"
    bitstream.write_bytes(b"rebuilt without gates")
    check = _gate(contract, contract_dir)
    assert check.status == "fail" and "differs" in check.detail
    bitstream.unlink()
    check = _gate(contract, contract_dir)
    assert check.status == "unknown"
    assert run_gates(contract, contract_dir).verdict == "unknown"


def test_changed_or_missing_artifact(tmp_path: Path) -> None:
    contract, contract_dir, artifact_path = _imported(tmp_path, _artifact())
    artifact_path.write_text(json.dumps(_artifact(device_ref="U9")), encoding="utf-8")
    assert _gate(contract, contract_dir).status == "fail"
    artifact_path.unlink()
    assert _gate(contract, contract_dir).status == "unknown"


@pytest.mark.parametrize(
    "changes",
    [
        {"artifact_kind": "fpga_pinmap"},
        {"system": "circuit"},
        {"extra": 1},
        {"bitstream_sha256": "0" * 63},
        {"bitstream": "/abs/blinky.bit"},
        {"board": None, "cable": None},
        {"argv": ["sh", "-c", "../build/blinky.bit"]},
        {"argv": ["openFPGALoader", "-b", "ulx3s", "../build/blinky.bit"]},
        {"bitstream_bytes": 0},
    ],
)
def test_malformed_artifact_is_rejected(changes: dict[str, Any]) -> None:
    data = _artifact(**changes)
    with pytest.raises(ValidationError):
        FpgaProductionSource.model_validate(data)
    with pytest.raises(ValueError, match="malformed fpga-production"):
        extract_import("fpga-production", data)


def test_import_rejects_malformed_artifact(tmp_path: Path) -> None:
    contract_path, artifact_path = _workspace(tmp_path, _artifact(extra=1))
    with pytest.raises(ValueError, match="malformed fpga-production"):
        import_source(
            load_contract(contract_path), "fpga-production", artifact_path, contract_path.parent
        )


def test_programs_must_reference_an_imported_device(tmp_path: Path) -> None:
    contract, _, _ = _imported(tmp_path, _artifact())
    with pytest.raises(ValidationError, match="no fpga-production import"):
        _bound(contract, ["U7"])
    with pytest.raises(ValidationError, match="twice"):
        _bound(contract, ["U1", "U1"])
    data = contract.model_dump(mode="json")
    data["operations"][0]["programs"] = ["U1"]
    assert data["operations"][0]["kind"] != "programming"
    with pytest.raises(ValidationError, match="not programming"):
        ProdengContract.model_validate(data)
