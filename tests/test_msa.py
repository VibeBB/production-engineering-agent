from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from prodeng.contract import ProdengContract
from prodeng.gates import GateReport, run_gates

EXAMPLE = Path(__file__).parents[1] / "examples" / "smart-kettle" / "smart-kettle.prodeng.json"
GAUGE = {"resolution": 0.01, "grr_pct_max": 10, "source": "Earth-bond tester datasheet"}


def _payload() -> dict[str, Any]:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def _item(payload: dict[str, Any], key: str, item_id: str) -> dict[str, Any]:
    return next(item for item in payload[key] if item["id"] == item_id)


def _run(payload: dict[str, Any]) -> GateReport:
    return run_gates(ProdengContract.model_validate(payload), EXAMPLE.parent)


def _status(report: GateReport, check_id: str, subject: str) -> str:
    return next(c.status for c in report.checks if c.id == check_id and c.subject == subject)


def test_msa_gates_absent_unless_declared() -> None:
    report = _run(_payload())
    assert not {"msa.resolution", "msa.grr", "capability.cpk_target"} & {
        check.id for check in report.checks
    }


# IN-04 measures critical CH-02 earth bond [0, 0.1] ohm: tolerance/10 = 0.01 ohm.
@pytest.mark.parametrize(
    ("resolution", "grr", "resolution_status", "grr_status"),
    [(0.01, 10, "pass", "pass"), (0.0101, 10.01, "fail", "fail")],
)
def test_gauge_boundaries(
    resolution: float, grr: float, resolution_status: str, grr_status: str
) -> None:
    payload = _payload()
    _item(payload, "inspections", "IN-04")["gauge"] = {
        **GAUGE,
        "resolution": resolution,
        "grr_pct_max": grr,
    }
    report = _run(payload)
    assert _status(report, "msa.resolution", "IN-04") == resolution_status
    assert _status(report, "msa.grr", "IN-04") == grr_status


def test_major_grr_allows_thirty_percent() -> None:
    payload = _payload()
    _item(payload, "characteristics", "CH-02")["classification"] = "major"
    _item(payload, "inspections", "IN-04")["gauge"] = {**GAUGE, "grr_pct_max": 30}
    assert _status(_run(payload), "msa.grr", "IN-04") == "pass"
    _item(payload, "inspections", "IN-04")["gauge"]["grr_pct_max"] = 30.01
    assert _status(_run(payload), "msa.grr", "IN-04") == "fail"


def test_one_sided_tolerance_is_unknown_and_attribute_gauge_fails() -> None:
    payload = _payload()
    del _item(payload, "characteristics", "CH-02")["lsl"]
    _item(payload, "inspections", "IN-04")["gauge"] = GAUGE
    _item(payload, "inspections", "IN-01")["gauge"] = GAUGE
    report = _run(payload)
    assert _status(report, "msa.resolution", "IN-04") == "unknown"
    assert _status(report, "msa.resolution", "IN-01") == "fail"
    assert report.verdict == "fail"


@pytest.mark.parametrize(
    ("classification", "cpk", "status"),
    [
        ("critical", 1.67, "pass"),
        ("critical", 1.66, "fail"),
        ("major", 1.33, "pass"),
        ("minor", 1.32, "fail"),
    ],
)
def test_cpk_target_boundaries(classification: str, cpk: float, status: str) -> None:
    payload = _payload()
    characteristic = _item(payload, "characteristics", "CH-02")
    characteristic.update(classification=classification, cpk_min=cpk)
    assert _status(_run(payload), "capability.cpk_target", "CH-02") == status


@pytest.mark.parametrize(
    ("key", "item_id", "field", "value"),
    [
        ("characteristics", "CH-01", "cpk_min", 1.67),
        ("characteristics", "CH-02", "cpk_min", 0),
        ("inspections", "IN-04", "gauge", {**GAUGE, "resolution": 0}),
        ("inspections", "IN-04", "gauge", {**GAUGE, "grr_pct_max": 101}),
        ("inspections", "IN-04", "gauge", {**GAUGE, "source": ""}),
    ],
)
def test_invalid_msa_fields_are_rejected(key: str, item_id: str, field: str, value: object) -> None:
    payload = _payload()
    _item(payload, key, item_id)[field] = value
    with pytest.raises(ValidationError):
        ProdengContract.model_validate(payload)
