from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from prodeng.contract import load_contract

EXAMPLE = Path(__file__).parents[1] / "examples" / "smart-kettle" / "smart-kettle.prodeng.json"
Invalidation = Callable[[dict[str, Any]], object]


def _payload() -> dict[str, Any]:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


INVALIDATIONS: list[Invalidation] = [
    lambda data: data["operations"].append(copy.deepcopy(data["operations"][0])),
    lambda data: data["inspections"][0].update(operation="OP99"),
    lambda data: data["characteristics"][0].update(criterion="", lsl=None, usl=None),
    lambda data: data["characteristics"][2].update(criterion=""),
    lambda data: data["characteristics"][1].update(lsl=1, usl=0),
    lambda data: data.pop("factory_test_mode"),
]


@pytest.mark.parametrize(
    "change",
    INVALIDATIONS,
    ids=[
        "duplicate-id",
        "dangling-reference",
        "variable-without-limits",
        "attribute-without-criterion",
        "lsl-above-usl",
        "ftm-command-without-ftm",
    ],
)
def test_load_time_schema_and_reference_rejections(tmp_path: Path, change: Invalidation) -> None:
    payload = _payload()
    change(payload)
    path = tmp_path / "invalid.prodeng.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        load_contract(path)


def test_volume_takt_seconds() -> None:
    contract = load_contract(EXAMPLE)
    assert contract.volume.takt_s == 72
