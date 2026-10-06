"""Boundary, decision-table and property tests for the deterministic gates.

Techniques follow docs/test-coverage.md: 3-value boundaries (below / on /
above, with ``math.nextafter`` for float limits), decision tables for
combined guards, equivalence classes over the ISO 2859-1 tables, and
fail-closed cases where a gate cannot decide.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from prodeng.contract import Characteristic, ProdengContract, Requirement, SamplingSpec
from prodeng.gates import GateReport, run_gates
from prodeng.sampling import (
    _DIAGONAL,  # pyright: ignore[reportPrivateUsage]
    _TABLE_1,  # pyright: ignore[reportPrivateUsage]
    _ZERO_DIAGONAL,  # pyright: ignore[reportPrivateUsage]
    AQL_VALUES,
    CODE_LETTERS,
    LEVELS,
    SAMPLE_SIZES,
    _cell,  # pyright: ignore[reportPrivateUsage]
    code_letter,
    sampling_plan,
)

EXAMPLE = Path(__file__).parents[1] / "examples" / "smart-kettle" / "smart-kettle.prodeng.json"
Mutation = Callable[[dict[str, Any]], object]
UP = math.inf
DOWN = -math.inf
TAKT_S = 72.0  # 250 days x 1 shift x 480 min x 60 s / 100000 units
FTM_BUDGET_S = 3.5  # TC-01 2000 ms + TC-02 1500 ms


def _report(change: Mutation) -> GateReport:
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    change(payload)
    return run_gates(ProdengContract.model_validate(payload), EXAMPLE.parent)


def _statuses(report: GateReport, check_id: str, subject: str | None = None) -> list[str]:
    return [
        check.status
        for check in report.checks
        if check.id == check_id and (subject is None or check.subject == subject)
    ]


def _operation(payload: dict[str, Any], op_id: str) -> dict[str, Any]:
    return next(item for item in payload["operations"] if item["id"] == op_id)


def _set(path: list[str | int], value: object) -> Mutation:
    def change(payload: dict[str, Any]) -> None:
        target: Any = payload
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

    return change


# ------------------------------------------------------------- ISO 2859-1


def test_takt_constant_matches_the_example() -> None:
    contract = ProdengContract.model_validate_json(EXAMPLE.read_text(encoding="utf-8"))
    assert contract.volume.takt_s == TAKT_S


@pytest.mark.parametrize("level", LEVELS)
def test_table_1_lot_edges(level: str) -> None:
    column = LEVELS.index(level)  # pyright: ignore[reportArgumentType]
    lower = 2
    for upper, letters in _TABLE_1:
        assert code_letter(lower, level) == letters[column]  # pyright: ignore[reportArgumentType]
        if upper is None:
            assert code_letter(10**9, level) == letters[column]  # pyright: ignore[reportArgumentType]
            break
        assert code_letter(upper, level) == letters[column]  # pyright: ignore[reportArgumentType]
        lower = upper + 1


@pytest.mark.parametrize(("lot", "ok"), [(1, False), (2, True), (3, True), (0, False)])
def test_lot_size_lower_boundary(lot: int, ok: bool) -> None:
    if ok:
        assert code_letter(lot, "II") == "A"
    else:
        with pytest.raises(ValueError, match="lot size"):
            code_letter(lot, "II")


def test_table_1_letters_never_decrease_with_lot_size_or_level() -> None:
    ranks = [[CODE_LETTERS.index(c) for c in letters] for _, letters in _TABLE_1]
    for row in ranks:
        assert row[4:] == sorted(row[4:])  # general levels I <= II <= III
        assert row[:4] == sorted(row[:4])  # special levels S-1 <= ... <= S-4
    for column in range(len(LEVELS)):
        values = [row[column] for row in ranks]
        assert values == sorted(values)


@pytest.mark.parametrize(
    ("delta", "ok"), [(0.0, True), (5e-10, True), (-5e-10, True), (2e-9, False), (-2e-9, False)]
)
def test_aql_matching_tolerance(delta: float, ok: bool) -> None:
    if ok:
        assert sampling_plan(1000, 1.0 + delta).code_letter == "J"
    else:
        with pytest.raises(ValueError, match="AQL"):
            sampling_plan(1000, 1.0 + delta)


@pytest.mark.parametrize(
    ("offset", "expected"),
    [
        (-1, "down"),
        (0, _DIAGONAL[0]),
        (len(_DIAGONAL) - 1, _DIAGONAL[-1]),
        (len(_DIAGONAL), "up"),
        (len(_DIAGONAL) + 1, "up"),
    ],
)
def test_diagonal_offset_boundaries(offset: int, expected: object) -> None:
    aql_index = AQL_VALUES.index(1.0)
    letter_index = offset + _ZERO_DIAGONAL - aql_index
    assert _cell(letter_index, aql_index) == expected


def test_every_sampling_plan_is_consistent() -> None:
    lots = sorted(
        {2, 3, 10**6}
        | {upper for upper, _ in _TABLE_1 if upper is not None}
        | {upper + 1 for upper, _ in _TABLE_1 if upper is not None}
    )
    for lot in lots:
        for level in LEVELS:
            for aql in AQL_VALUES:
                plan = sampling_plan(lot, aql, level)
                assert plan.reject == plan.accept + 1
                assert plan.full_inspection == (SAMPLE_SIZES[plan.code_letter] >= lot)
                if plan.full_inspection:
                    assert (plan.sample_size, plan.accept) == (lot, 0)
                else:
                    assert plan.sample_size == SAMPLE_SIZES[plan.code_letter] < lot
                    assert plan.accept < plan.sample_size


def test_acceptance_number_grows_with_aql_for_a_fixed_plan_letter() -> None:
    for letter_index in range(len(CODE_LETTERS)):
        accepts = [
            cell[0]
            for aql_index in range(len(AQL_VALUES))
            if not isinstance(cell := _cell(letter_index, aql_index), str)
        ]
        assert accepts == sorted(accepts)


# ------------------------------------------------------------ takt / FTM


@pytest.mark.parametrize(
    ("cycle", "status"),
    [
        (math.nextafter(TAKT_S, DOWN), "pass"),
        (TAKT_S, "pass"),
        (math.nextafter(TAKT_S, UP), "fail"),
    ],
)
def test_station_takt_three_value_boundary(cycle: float, status: str) -> None:
    report = _report(lambda p: _operation(p, "OP01").update(cycle_time_s=cycle))
    assert _statuses(report, "takt.station", "SMT") == [status]


def test_station_with_unmeasured_cycle_is_unknown() -> None:
    report = _report(lambda p: _operation(p, "OP01").pop("cycle_time_s"))
    assert _statuses(report, "takt.station", "SMT") == ["unknown"]
    assert report.verdict != "pass"


def test_station_total_sums_operations() -> None:
    def change(payload: dict[str, Any]) -> None:
        _operation(payload, "OP01").update(cycle_time_s=40.0)
        _operation(payload, "OP02").update(station="SMT", cycle_time_s=32.0)

    assert _statuses(_report(change), "takt.station", "SMT") == ["pass"]

    def over(payload: dict[str, Any]) -> None:
        change(payload)
        _operation(payload, "OP02").update(cycle_time_s=32.5)

    assert _statuses(_report(over), "takt.station", "SMT") == ["fail"]


@pytest.mark.parametrize(
    ("maximum", "status"),
    [
        (math.nextafter(FTM_BUDGET_S, DOWN), "fail"),
        (FTM_BUDGET_S, "pass"),
        (math.nextafter(FTM_BUDGET_S, UP), "pass"),
    ],
)
def test_ftm_duration_three_value_boundary(maximum: float, status: str) -> None:
    report = _report(_set(["factory_test_mode", "max_duration_s"], maximum))
    assert _statuses(report, "ftm.duration") == [status]


@pytest.mark.parametrize(
    ("cycle", "status"),
    [
        (math.nextafter(FTM_BUDGET_S, DOWN), "fail"),
        (FTM_BUDGET_S, "pass"),
        (math.nextafter(FTM_BUDGET_S, UP), "pass"),
    ],
)
def test_ftm_station_fit_three_value_boundary(cycle: float, status: str) -> None:
    report = _report(lambda p: _operation(p, "OP03").update(cycle_time_s=cycle))
    assert _statuses(report, "ftm.station_fit", "OP03") == [status]


def test_ftm_station_fit_unknown_without_cycle_time() -> None:
    report = _report(lambda p: _operation(p, "OP03").pop("cycle_time_s"))
    assert _statuses(report, "ftm.station_fit", "OP03") == ["unknown"]


@pytest.mark.parametrize(("count", "status"), [(1, "fail"), (2, "pass"), (3, "pass")])
def test_ftm_entry_guard_three_value_boundary(count: int, status: str) -> None:
    conditions = [f"condition {index}" for index in range(count)]
    report = _report(_set(["factory_test_mode", "entry", "conditions"], conditions))
    assert _statuses(report, "ftm.entry_guard") == [status]


@pytest.mark.parametrize(("method", "status"), [("none", "fail"), ("nvm_flag", "pass")])
def test_ftm_lockout(method: str, status: str) -> None:
    report = _report(_set(["factory_test_mode", "field_lockout", "method"], method))
    assert _statuses(report, "ftm.lockout") == [status]


# covers x used-by decision table for one command.
@pytest.mark.parametrize(
    ("covers", "used", "status"),
    [(True, True, "pass"), (False, True, "fail"), (True, False, "fail"), (False, False, "fail")],
)
def test_ftm_command_used_decision_table(covers: bool, used: bool, status: str) -> None:
    def change(payload: dict[str, Any]) -> None:
        command = payload["factory_test_mode"]["commands"][1]
        if not covers:
            command["covers"] = []
        if not used:
            for inspection in payload["inspections"]:
                inspection["ftm_commands"] = [
                    item for item in inspection["ftm_commands"] if item != "TC-02"
                ]

    assert _statuses(_report(change), "ftm.command_used", "TC-02") == [status]


def test_ftm_present_only_required_by_fct() -> None:
    def no_fct(payload: dict[str, Any]) -> None:
        payload["inspections"][1]["method"] = "visual"

    assert _statuses(_report(no_fct), "ftm.present") == []

    def no_ftm(payload: dict[str, Any]) -> None:
        payload["factory_test_mode"] = None
        for inspection in payload["inspections"]:
            inspection["ftm_commands"] = []

    report = _report(no_ftm)
    assert _statuses(report, "ftm.present") == ["fail"]
    assert _statuses(report, "ftm.duration") == []


# ---------------------------------------------------------------- PFMEA


@pytest.mark.parametrize(("severity", "statuses"), [(8, []), (9, ["pass"]), (10, ["pass"])])
def test_high_severity_threshold(severity: int, statuses: list[str]) -> None:
    report = _report(_set(["failure_modes", 1, "severity"], severity))
    assert _statuses(report, "pfmea.high_severity", "FM-02") == statuses


def test_high_severity_needs_a_full_inspection_control() -> None:
    report = _report(_set(["failure_modes", 0, "controls"], ["IN-01"]))
    assert _statuses(report, "pfmea.high_severity", "FM-01") == ["fail"]
    assert _statuses(report, "pfmea.controls", "FM-01") == ["pass"]
    assert report.verdict == "fail"


def test_failure_mode_without_controls_fails() -> None:
    report = _report(_set(["failure_modes", 1, "controls"], []))
    assert _statuses(report, "pfmea.controls", "FM-02") == ["fail"]


# ----------------------------------------------------- work instructions


# hazards x precautions x linked hipot/ground-bond test.
@pytest.mark.parametrize(
    ("op_id", "hazards", "precautions", "status"),
    [
        ("OP03", [], [], "pass"),
        ("OP03", ["hot surface"], [], "fail"),
        ("OP03", ["hot surface"], ["wear gloves"], "pass"),
        ("OP03", [], ["wear gloves"], "pass"),
        ("OP05", [], ["interlocked cage"], "fail"),
        ("OP05", ["high voltage"], [], "fail"),
        ("OP05", ["high voltage"], ["interlocked cage"], "pass"),
    ],
)
def test_work_instruction_safety_decision_table(
    op_id: str, hazards: list[str], precautions: list[str], status: str
) -> None:
    report = _report(
        lambda p: _operation(p, op_id).update(
            safety_hazards=hazards, safety_precautions=precautions
        )
    )
    assert _statuses(report, "work_instruction.safety", op_id) == [status]


WORK_STEPS: list[tuple[list[dict[str, Any]], str]] = [
    ([], "fail"),
    ([{"step": "Load panel", "key_points": []}], "fail"),
    ([{"step": "Load panel", "key_points": ["fiducial up"]}], "pass"),
    (
        [
            {"step": "Load panel", "key_points": ["fiducial up"]},
            {"step": "Start", "key_points": []},
        ],
        "fail",
    ),
]


@pytest.mark.parametrize(("elements", "status"), WORK_STEPS)
def test_work_instruction_steps(elements: list[dict[str, Any]], status: str) -> None:
    report = _report(lambda p: _operation(p, "OP01").update(work_elements=elements))
    assert _statuses(report, "work_instruction.steps", "OP01") == [status]


# ------------------------------------------------------- contract schema


def _characteristic(**fields: Any) -> Characteristic:
    base: dict[str, Any] = {
        "id": "CH-01",
        "description": "heater resistance",
        "classification": "major",
        "kind": "variable",
        "unit": "ohm",
        "lsl": 10.0,
        "usl": 12.0,
        "sources": ["R001"],
    }
    return Characteristic.model_validate({**base, **fields})


@pytest.mark.parametrize(
    ("fields", "ok"),
    [
        ({"lsl": 12.0, "usl": 12.0}, True),
        ({"lsl": math.nextafter(12.0, UP), "usl": 12.0}, False),
        ({"nominal": 10.0}, True),
        ({"nominal": math.nextafter(10.0, DOWN)}, False),
        ({"nominal": 12.0}, True),
        ({"nominal": math.nextafter(12.0, UP)}, False),
        ({"lsl": None, "nominal": -5.0}, True),
        ({"usl": None, "nominal": 50.0}, True),
        ({"lsl": None, "usl": None}, False),
        ({"unit": ""}, False),
        ({"unit": None}, False),
    ],
)
def test_variable_characteristic_limits(fields: dict[str, Any], ok: bool) -> None:
    if ok:
        _characteristic(**fields)
    else:
        with pytest.raises(ValidationError):
            _characteristic(**fields)


@pytest.mark.parametrize(("criterion", "ok"), [("", False), ("IPC-A-610 class 2", True)])
def test_attribute_characteristic_requires_criterion(criterion: str, ok: bool) -> None:
    fields = {"kind": "attribute", "unit": None, "lsl": None, "usl": None, "criterion": criterion}
    if ok:
        assert _characteristic(**fields).kind == "attribute"
    else:
        with pytest.raises(ValidationError, match="criterion"):
            _characteristic(**fields)


@pytest.mark.parametrize(
    ("spec", "ok"),
    [
        ({"mode": "aql", "aql": 1.0}, True),
        ({"mode": "aql"}, False),
        ({"mode": "aql", "aql": 0.3}, False),
        ({"mode": "full"}, True),
        ({"mode": "full", "aql": 1.0}, False),
    ],
)
def test_sampling_spec_decision_table(spec: dict[str, Any], ok: bool) -> None:
    if ok:
        SamplingSpec.model_validate(spec)
    else:
        with pytest.raises(ValidationError):
            SamplingSpec.model_validate(spec)


@pytest.mark.parametrize(
    ("req_id", "kind", "ok"),
    [
        ("R1", "requirement", True),
        ("A1", "assumption", True),
        ("Q1", "question", True),
        ("R1", "assumption", False),
        ("Q1", "requirement", False),
    ],
)
def test_requirement_prefix_matches_kind(req_id: str, kind: str, ok: bool) -> None:
    payload = {"id": req_id, "kind": kind, "text": "x"}
    if ok:
        Requirement.model_validate(payload)
    else:
        with pytest.raises(ValidationError, match="requires kind"):
            Requirement.model_validate(payload)


def test_open_question_is_unknown() -> None:
    def change(payload: dict[str, Any]) -> None:
        payload["requirements"].append(
            {"id": "Q9", "kind": "question", "text": "Which fixture?", "status": "open"}
        )

    report = _report(change)
    assert _statuses(report, "requirements.open_questions", "Q9") == ["unknown"]
    assert report.verdict != "pass"
