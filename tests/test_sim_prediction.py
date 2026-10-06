from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from prodeng.contract import ProdengContract
from prodeng.gates import GateCheck, run_gates

EXAMPLE = Path(__file__).parents[1] / "examples" / "smart-kettle" / "smart-kettle.prodeng.json"
ROW = {"id": "pdn.3V3.drop", "verdict": "pass", "measured": 0.04, "limit": "≤ 0.1 V"}


def _report(tmp_path: Path, rows: list[dict[str, Any]] | str) -> tuple[str, str]:
    path = tmp_path / "sim" / "sim-report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = rows if isinstance(rows, str) else json.dumps({"verdict": "pass", "checks": rows})
    path.write_text(text, encoding="utf-8")
    return "sim/sim-report.json", hashlib.sha256(path.read_bytes()).hexdigest()


def _gate(tmp_path: Path, rows: list[dict[str, Any]] | str, **changes: Any) -> GateCheck:
    report_path, sha = _report(tmp_path, rows)
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    characteristic = next(item for item in payload["characteristics"] if item["id"] == "CH-02")
    characteristic["simulation"] = {
        "report_path": report_path,
        "sha256": sha,
        "check_id": ROW["id"],
        **changes,
    }
    contract = ProdengContract.model_validate(payload)
    (tmp_path / "upstream").mkdir(exist_ok=True)
    for imported in contract.imports:
        source = EXAMPLE.parent / imported.path
        (tmp_path / imported.path).write_bytes(source.read_bytes())
    report = run_gates(contract, tmp_path)
    (check,) = [item for item in report.checks if item.id == "sim.prediction"]
    return check


def test_prediction_inside_window_passes_with_headroom(tmp_path: Path) -> None:
    check = _gate(tmp_path, [ROW])
    assert check.status == "pass"
    assert check.subject == "CH-02"
    assert check.measured == 0.04
    assert check.limit == "[0, 0.1] ohm"
    assert "headroom 0.04 (40% of tolerance)" in check.detail


@pytest.mark.parametrize(
    ("rows", "changes", "status", "detail"),
    [
        ([{**ROW, "measured": 0.12}], {}, "fail", "outside the production window"),
        ([{**ROW, "measured": -0.01}], {}, "fail", "outside the production window"),
        ([{**ROW, "verdict": "fail"}], {}, "fail", "simulation fails"),
        ([{**ROW, "verdict": "unknown"}], {}, "unknown", "verdict"),
        ([{**ROW, "measured": None}], {}, "unknown", "finite"),
        ([{**ROW, "measured": True}], {}, "unknown", "finite"),
        ([{**ROW, "measured": "0.04"}], {}, "unknown", "finite"),
        ([], {}, "unknown", "no single check"),
        ([ROW, ROW], {}, "unknown", "no single check"),
        ("not json", {}, "unknown", "not JSON"),
        ([ROW], {"sha256": "0" * 64}, "fail", "sha256 mismatch"),
        ([ROW], {"report_path": "sim/missing.json"}, "unknown", "missing"),
    ],
)
def test_prediction_fails_closed(
    tmp_path: Path,
    rows: list[dict[str, Any]] | str,
    changes: dict[str, Any],
    status: str,
    detail: str,
) -> None:
    check = _gate(tmp_path, rows, **changes)
    assert check.status == status
    assert detail in check.detail


def test_boundary_prediction_is_inside(tmp_path: Path) -> None:
    assert _gate(tmp_path, [{**ROW, "measured": 0.1}]).status == "pass"


def test_attribute_characteristic_rejects_prediction() -> None:
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    payload["characteristics"][0]["simulation"] = {
        "report_path": "sim/r.json",
        "sha256": "0" * 64,
        "check_id": "x",
    }
    with pytest.raises(ValueError, match="variable characteristic"):
        ProdengContract.model_validate(payload)
