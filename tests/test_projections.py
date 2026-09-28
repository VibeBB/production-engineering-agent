from __future__ import annotations

from pathlib import Path

from prodeng.contract import load_contract
from prodeng.gates import run_gates
from prodeng.projections import write_projections
from prodeng.report import write_report
from prodeng.requests import write_requests

EXAMPLE_DIR = Path(__file__).parents[1] / "examples" / "smart-kettle"


def test_projections_are_byte_stable_against_committed_golden(tmp_path: Path) -> None:
    contract = load_contract(EXAMPLE_DIR / "smart-kettle.prodeng.json")
    paths = write_projections(contract, "smart-kettle", tmp_path)
    gates = run_gates(contract, EXAMPLE_DIR)
    write_requests(contract, gates, tmp_path)
    paths.update(write_report(contract, gates, tmp_path, tmp_path))
    golden = EXAMPLE_DIR / "out" / "smart-kettle"
    for path in paths.values():
        assert path.read_bytes() == (golden / path.name).read_bytes(), path.name


def test_work_instruction_and_factory_spec_include_required_sections(tmp_path: Path) -> None:
    contract = load_contract(EXAMPLE_DIR / "smart-kettle.prodeng.json")
    paths = write_projections(contract, "smart-kettle", tmp_path)
    instructions = paths["work_instructions"].read_text(encoding="utf-8")
    assert "| Major step | Key points | Reasons |" in instructions
    assert "Tools:" in instructions
    assert "Fixtures:" in instructions
    assert "ESD:" in instructions
    assert "Safety precautions:" in instructions
    assert "Linked inspections:" in instructions
    factory_spec = paths["factory_test_markdown"].read_text(encoding="utf-8")
    for section in (
        "Entry",
        "Field lockout",
        "Interface",
        "Commands",
        "Provisioning",
        "Exit",
        "Duration budget",
    ):
        assert f"## {section}" in factory_spec
