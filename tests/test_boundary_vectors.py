"""boundary-vectors.json: 3-value boundary stimuli per gauged variable inspection."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from prodeng.contract import Gauge, load_contract
from prodeng.projections import boundary_vectors

EXAMPLE = Path(__file__).parents[1] / "examples" / "smart-kettle" / "smart-kettle.prodeng.json"


def _gauged(**limits: float | None) -> dict[str, Any]:
    contract = load_contract(EXAMPLE)
    inspection = next(i for i in contract.inspections if i.characteristic == "CH-02")
    characteristics = [
        c.model_copy(update=limits) if c.id == "CH-02" else c for c in contract.characteristics
    ]
    gauge = Gauge(resolution=0.01, grr_pct_max=10, source="gauge datasheet")
    inspections = [
        i.model_copy(update={"gauge": gauge}) if i.id == inspection.id else i
        for i in contract.inspections
    ]
    updated = contract.model_copy(
        update={"characteristics": characteristics, "inspections": inspections}
    )
    return boundary_vectors(updated)


def _cases(result: dict[str, Any]) -> list[tuple[str, float, str]]:
    (vector,) = result["vectors"]
    return [(c["limit"], c["value"], c["expect"]) for c in vector["cases"]]


def test_upper_limit_gets_below_on_and_above() -> None:
    assert _cases(_gauged(lsl=None, usl=0.1)) == [
        ("usl", 0.09, "pass"),
        ("usl", 0.1, "pass"),
        ("usl", 0.11, "fail"),
    ]


def test_two_sided_limits_fail_outside_each_side() -> None:
    assert _cases(_gauged(lsl=0.05, usl=0.1)) == [
        ("lsl", 0.04, "fail"),
        ("lsl", 0.05, "pass"),
        ("lsl", 0.06, "pass"),
        ("usl", 0.09, "pass"),
        ("usl", 0.1, "pass"),
        ("usl", 0.11, "fail"),
    ]


def test_step_past_the_other_limit_expects_fail() -> None:
    cases = _cases(_gauged(lsl=0.1, usl=0.105, nominal=None))
    assert ("lsl", 0.11, "fail") in cases and ("usl", 0.095, "fail") in cases


def test_gauge_less_variable_inspections_are_unsized() -> None:
    result = boundary_vectors(load_contract(EXAMPLE))
    assert result["vectors"] == []
    assert result["unsized"]
