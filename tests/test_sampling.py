from __future__ import annotations

import pytest

from prodeng.sampling import InspectionLevel, sampling_plan

EXAMPLES: list[tuple[int, float, InspectionLevel, tuple[str, int, int, int, bool]]] = [
    (1000, 1.0, "II", ("J", 80, 2, 3, False)),
    (500, 0.65, "II", ("J", 80, 1, 2, False)),
    (3000, 1.5, "II", ("K", 125, 5, 6, False)),
    (10, 1.0, "II", ("E", 10, 0, 1, True)),
    (200, 2.5, "II", ("G", 32, 2, 3, False)),
    (50, 0.10, "II", ("K", 50, 0, 1, True)),
    (100000, 0.010, "II", ("Q", 1250, 0, 1, False)),
    (1000000, 0.015, "III", ("P", 800, 0, 1, False)),
    (1000, 4.0, "S-3", ("E", 13, 1, 2, False)),
    (5, 6.5, "II", ("A", 2, 0, 1, False)),
    (1300, 10.0, "I", ("H", 50, 10, 11, False)),
]


@pytest.mark.parametrize(("lot", "aql", "level", "expected"), EXAMPLES)
def test_iso_sampling_examples(
    lot: int,
    aql: float,
    level: InspectionLevel,
    expected: tuple[str, int, int, int, bool],
) -> None:
    plan = sampling_plan(lot, aql, level)
    assert (
        plan.code_letter,
        plan.sample_size,
        plan.accept,
        plan.reject,
        plan.full_inspection,
    ) == expected


@pytest.mark.parametrize(("lot", "aql"), [(1, 1.0), (100, 0.3)])
def test_sampling_rejects_invalid_input(lot: int, aql: float) -> None:
    with pytest.raises(ValueError):
        sampling_plan(lot, aql)
