from __future__ import annotations

import csv
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
    request_paths = write_requests(contract, gates, tmp_path)
    paths.update(write_report(contract, gates, tmp_path, tmp_path))
    golden = EXAMPLE_DIR / "out" / "smart-kettle"
    for path in paths.values():
        assert path.read_bytes() == (golden / path.name).read_bytes(), path.name
    for path in request_paths:
        assert path.read_bytes() == (EXAMPLE_DIR / path.name).read_bytes(), path.name


def test_safety_inspections_use_distinct_characteristics_and_process_order(
    tmp_path: Path,
) -> None:
    contract = load_contract(EXAMPLE_DIR / "smart-kettle.prodeng.json")
    characteristics = {item.id: item for item in contract.characteristics}
    inspections = {item.id: item for item in contract.inspections}
    assert characteristics["CH-02"].description == "Protective-earth bond resistance"
    assert characteristics["CH-02"].usl == 0.1
    assert characteristics["CH-05"].description == "Dielectric withstand leakage current"
    assert characteristics["CH-05"].usl == 5.0
    assert inspections["IN-03"].method == "hipot"
    assert inspections["IN-03"].characteristic == "CH-05"
    assert inspections["IN-04"].method == "ground_bond"
    assert inspections["IN-04"].characteristic == "CH-02"
    paths = write_projections(contract, "smart-kettle", tmp_path)
    with paths["line_balance"].open(encoding="utf-8", newline="") as file:
        rows = list(csv.reader(file))
    assert [row[0] for row in rows[1:]] == [
        "SMT",
        "THT",
        "PROGRAM-FCT",
        "ASSEMBLY",
        "SAFETY-TEST",
        "PACK",
    ]


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
