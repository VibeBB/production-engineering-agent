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
from prodeng.imports import FirmwareProductionSource, extract_import, import_source
from prodeng.projections import ftm_spec_bytes

EXAMPLE = Path(__file__).parents[1] / "examples" / "smart-kettle"
FIXTURE = Path(__file__).parent / "fixtures" / "upstream" / "smart-kettle.fw-production.json"
FPGA_FIXTURE = Path(__file__).parent / "fixtures" / "upstream" / "blinky.fpga-production.json"
ELF = b"\x7fELF gated firmware image" * 64


def _artifact(**changes: Any) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data.update(elf_sha256=hashlib.sha256(ELF).hexdigest(), elf_bytes=len(ELF))
    data.update(changes)
    return data


def _workspace(tmp_path: Path, artifact: dict[str, Any]) -> tuple[Path, Path]:
    shutil.copytree(EXAMPLE, tmp_path / "smart-kettle")
    reports = tmp_path / "firmware" / "fw-reports"
    reports.mkdir(parents=True)
    (tmp_path / "firmware" / "fw" / "build").mkdir(parents=True)
    (tmp_path / "firmware" / "fw" / "build" / "smart-kettle.elf").write_bytes(ELF)
    path = reports / "smart-kettle.fw-production.json"
    path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    return tmp_path / "smart-kettle" / "smart-kettle.prodeng.json", path


def _bound(contract: ProdengContract, programs: list[str], **top: Any) -> ProdengContract:
    data = contract.model_dump(mode="json")
    data.update(top)
    if data.get("factory_test_mode") is None:
        for inspection in data["inspections"]:
            inspection["ftm_commands"] = []
    for operation in data["operations"]:
        if operation["id"] == "OP03":
            operation["programs"] = programs
    return ProdengContract.model_validate(data)


def _imported(
    tmp_path: Path, artifact: dict[str, Any], **top: Any
) -> tuple[ProdengContract, Path, Path]:
    contract_path, artifact_path = _workspace(tmp_path, artifact)
    contract = import_source(
        load_contract(contract_path), "firmware-production", artifact_path, contract_path.parent
    )
    return _bound(contract, ["U1"], **top), contract_path.parent, artifact_path


def _gate(contract: ProdengContract, contract_dir: Path) -> GateCheck:
    found = [c for c in run_gates(contract, contract_dir).checks if c.id == "firmware.programming"]
    assert len(found) == 1
    return found[0]


def test_real_firmware_agent_export_pins_this_factory_test_spec() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert extract_import("firmware-production", payload).parts == ["U1"]
    spec = ftm_spec_bytes(load_contract(EXAMPLE / "smart-kettle.prodeng.json"))
    assert payload["ftm_spec_sha256"] == hashlib.sha256(spec).hexdigest()
    assert (EXAMPLE / "out" / "smart-kettle" / "factory-test-spec.json").read_bytes() == spec


def test_gated_elf_serving_the_current_spec_passes(tmp_path: Path) -> None:
    contract, contract_dir, _ = _imported(tmp_path, _artifact())
    imported = [item for item in contract.imports if item.kind == "firmware-production"]
    assert imported[0].system == "firmware" and imported[0].extracted.parts == ["U1"]
    check = _gate(contract, contract_dir)
    assert check.status == "pass", check
    assert check.measured == check.limit == hashlib.sha256(ELF).hexdigest()
    assert "OP03 flashes ../fw/build/smart-kettle.elf on RP2040" in check.detail
    assert "serves TC-01, TC-02" in check.detail
    assert run_gates(contract, contract_dir).verdict == "pass"


def test_unbound_mcu_fails(tmp_path: Path) -> None:
    contract, contract_dir, _ = _imported(tmp_path, _artifact())
    check = _gate(_bound(contract, []), contract_dir)
    assert (check.status, check.detail) == ("fail", "no programming operation programs it")


def test_tampered_or_missing_elf(tmp_path: Path) -> None:
    contract, contract_dir, _ = _imported(tmp_path, _artifact())
    elf = tmp_path / "firmware" / "fw" / "build" / "smart-kettle.elf"
    elf.write_bytes(ELF + b"patch")
    check = _gate(contract, contract_dir)
    assert check.status == "fail" and "differs from the one firmware-agent gated" in check.detail
    elf.unlink()
    check = _gate(contract, contract_dir)
    assert check.status == "unknown" and "ELF unreadable" in check.detail


def test_changed_or_missing_artifact(tmp_path: Path) -> None:
    contract, contract_dir, artifact_path = _imported(tmp_path, _artifact())
    artifact_path.write_text(json.dumps(_artifact(elf_bytes=1)) + "\n", encoding="utf-8")
    assert _gate(contract, contract_dir).detail == "artifact changed since import"
    artifact_path.unlink()
    assert _gate(contract, contract_dir).status == "unknown"


def test_firmware_gated_against_another_spec_fails(tmp_path: Path) -> None:
    contract, contract_dir, _ = _imported(tmp_path, _artifact(ftm_spec_sha256="0" * 64))
    check = _gate(contract, contract_dir)
    assert check.status == "fail" and "re-pin ftm.sha256" in check.detail


def test_changed_factory_test_mode_invalidates_the_image(tmp_path: Path) -> None:
    contract, contract_dir, _ = _imported(tmp_path, _artifact())
    data = contract.model_dump(mode="json")
    data["factory_test_mode"]["commands"][0]["timeout_ms"] = 2500
    check = _gate(ProdengContract.model_validate(data), contract_dir)
    assert check.status == "fail" and "gated against factory test spec" in check.detail


def test_firmware_without_ftm_fails_when_the_contract_declares_one(tmp_path: Path) -> None:
    contract, contract_dir, _ = _imported(
        tmp_path, _artifact(ftm_spec_sha256=None, ftm_commands=[])
    )
    check = _gate(contract, contract_dir)
    assert check.status == "fail" and "gated without the factory test spec" in check.detail


def test_mismatched_command_set_fails(tmp_path: Path) -> None:
    contract, contract_dir, _ = _imported(tmp_path, _artifact(ftm_commands=["TC-01"]))
    check = _gate(contract, contract_dir)
    assert check.status == "fail" and "the spec declares ['TC-01', 'TC-02']" in check.detail


def test_ftm_presence_must_agree(tmp_path: Path) -> None:
    contract, contract_dir, _ = _imported(tmp_path, _artifact(), factory_test_mode=None)
    check = _gate(contract, contract_dir)
    assert check.status == "fail" and "no longer declares" in check.detail
    plain, plain_dir, _ = _imported(
        tmp_path / "plain",
        _artifact(ftm_spec_sha256=None, ftm_commands=[]),
        factory_test_mode=None,
    )
    check = _gate(plain, plain_dir)
    assert check.status == "pass" and "no factory test mode" in check.detail


@pytest.mark.parametrize(
    "changes",
    [
        {"artifact_kind": "fpga_production"},
        {"system": "fpga"},
        {"schema_version": 2},
        {"elf_sha256": "XYZ"},
        {"elf_bytes": 0},
        {"elf": "/abs/smart-kettle.elf"},
        {"ftm_commands": []},
        {"ftm_spec_sha256": None},
        {"ftm_commands": ["TC-01", "TC-01"]},
        {"ftm_commands": ["T1"]},
        {"extra": True},
    ],
)
def test_malformed_artifacts_are_rejected(tmp_path: Path, changes: dict[str, Any]) -> None:
    artifact = _artifact(**changes)
    with pytest.raises(ValidationError):
        FirmwareProductionSource.model_validate(artifact)
    with pytest.raises(ValueError, match="malformed firmware-production"):
        extract_import("firmware-production", artifact)


def test_one_device_from_one_programming_import(tmp_path: Path) -> None:
    contract, contract_dir, _ = _imported(tmp_path, _artifact())
    fpga = tmp_path / "fpga.fpga-production.json"
    shutil.copyfile(FPGA_FIXTURE, fpga)
    with pytest.raises(ValidationError, match="more than one programming import"):
        import_source(contract, "fpga-production", fpga, contract_dir)
