from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from prodeng.contract import ProdengContract, load_contract
from prodeng.gates import GateReport, run_gates

EXAMPLE = Path(__file__).parents[1] / "examples" / "smart-kettle" / "smart-kettle.prodeng.json"
Mutation = Callable[[dict[str, Any]], object]


def _payload() -> dict[str, Any]:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def _contract(change: Mutation | None = None) -> ProdengContract:
    payload = _payload()
    if change is not None:
        change(payload)
    return ProdengContract.model_validate(payload)


def _check(report: GateReport, check_id: str, subject: str | None = None) -> str:
    for check in report.checks:
        if check.id == check_id and (subject is None or check.subject == subject):
            return check.status
    raise AssertionError(f"missing gate check {check_id!r} for {subject!r}")


def test_example_has_pass_case_for_each_gate_id() -> None:
    contract = load_contract(EXAMPLE)
    report = run_gates(contract, EXAMPLE.parent)
    assert report.verdict == "pass"
    required = {
        "coverage.characteristic",
        "coverage.critical_full",
        "sampling.plan",
        "takt.station",
        "ftm.present",
        "ftm.entry_guard",
        "ftm.lockout",
        "ftm.duration",
        "ftm.station_fit",
        "ftm.command_used",
        "dft.test_access",
        "pfmea.controls",
        "pfmea.high_severity",
        "work_instruction.steps",
        "work_instruction.safety",
        "imports.fresh",
    }
    assert required <= {check.id for check in report.checks}
    assert all(check.status == "pass" for check in report.checks)


FAIL_CASES: list[tuple[str, Mutation, str]] = [
    (
        "coverage.characteristic",
        lambda data: data["characteristics"].append(
            {
                "id": "CH-99",
                "description": "Uninspected characteristic",
                "classification": "minor",
                "kind": "attribute",
                "criterion": "must be inspected",
                "sources": ["R002"],
            }
        ),
        "CH-99",
    ),
    (
        "coverage.critical_full",
        lambda data: [
            inspection["sampling"].update(mode="aql", aql=1.0)
            for inspection in data["inspections"]
            if inspection["characteristic"] == "CH-02"
        ],
        "CH-02",
    ),
    (
        "takt.station",
        lambda data: data["operations"][0].update(cycle_time_s=1000),
        "SMT",
    ),
    (
        "ftm.present",
        lambda data: (
            data.pop("factory_test_mode"),
            [inspection.update(ftm_commands=[]) for inspection in data["inspections"]],
        ),
        "smart-kettle",
    ),
    (
        "ftm.entry_guard",
        lambda data: data["factory_test_mode"]["entry"].update(conditions=["strap"]),
        "smart-kettle",
    ),
    (
        "ftm.lockout",
        lambda data: data["factory_test_mode"]["field_lockout"].update(method="none"),
        "smart-kettle",
    ),
    (
        "ftm.duration",
        lambda data: data["factory_test_mode"].update(max_duration_s=1),
        "smart-kettle",
    ),
    (
        "ftm.station_fit",
        lambda data: data["operations"][2].update(cycle_time_s=2),
        "OP03",
    ),
    (
        "ftm.command_used",
        lambda data: data["factory_test_mode"]["commands"][0].update(covers=[]),
        "TC-01",
    ),
    (
        "dft.test_access",
        lambda data: data["imports"][0]["extracted"].update(nets=[]),
        "FTM_STRAP",
    ),
    (
        "pfmea.controls",
        lambda data: data["failure_modes"][1].update(controls=[]),
        "FM-02",
    ),
    (
        "pfmea.high_severity",
        lambda data: data["failure_modes"][0].update(controls=["IN-01"]),
        "FM-01",
    ),
    (
        "work_instruction.steps",
        lambda data: data["operations"][0].update(work_elements=[]),
        "OP01",
    ),
    (
        "work_instruction.safety",
        lambda data: data["operations"][4].update(safety_hazards=[], safety_precautions=[]),
        "OP05",
    ),
    (
        "imports.fresh",
        lambda data: data["imports"][0].update(sha256="0" * 64),
        "upstream/smart-kettle.circuit-brief.json",
    ),
]


@pytest.mark.parametrize(("check_id", "mutate", "subject"), FAIL_CASES)
def test_gate_fail_cases(check_id: str, mutate: Mutation, subject: str) -> None:
    contract = _contract(mutate)
    report = run_gates(contract, EXAMPLE.parent)
    assert _check(report, check_id, subject) == "fail"
    assert report.verdict == "fail"


UNKNOWN_CASES: list[tuple[Mutation, str, str]] = [
    (
        lambda data: data["operations"][0].update(cycle_time_s=None),
        "takt.station",
        "SMT",
    ),
    (
        lambda data: data.update(imports=[]),
        "dft.test_access",
        "circuit import",
    ),
    (
        lambda data: data["imports"][0].update(path="missing.json"),
        "imports.fresh",
        "missing.json",
    ),
    (
        lambda data: next(item for item in data["requirements"] if item["id"] == "Q001").update(
            status="open"
        ),
        "requirements.open_questions",
        "Q001",
    ),
]


@pytest.mark.parametrize(("mutate", "check_id", "subject"), UNKNOWN_CASES)
def test_unknown_gate_cases(mutate: Mutation, check_id: str, subject: str) -> None:
    payload = _payload()
    mutate(payload)
    contract = ProdengContract.model_validate(payload)
    report = run_gates(contract, EXAMPLE.parent)
    assert _check(report, check_id, subject) == "unknown"
    assert report.verdict == "unknown"
