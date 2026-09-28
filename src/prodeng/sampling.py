"""ISO 2859-1 / JIS Z 9015-1 single sampling plans (normal inspection).

Implements Table 1 (sample size code letters) and Table 2-A (single
sampling, normal inspection) for AQL 0.010-10 % nonconforming. Table 2-A
is a diagonal table: along each diagonal (code letter index + AQL column
index) the acceptance number is constant, so the table is encoded as that
diagonal sequence. Arrow cells resolve to the first plan in the arrow's
direction within the same AQL column; when a sampling plan's sample size
reaches the lot size, inspection becomes 100 %.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

InspectionLevel = Literal["I", "II", "III", "S-1", "S-2", "S-3", "S-4"]

CODE_LETTERS: Final = "ABCDEFGHJKLMNPQR"
SAMPLE_SIZES: Final[dict[str, int]] = {
    "A": 2,
    "B": 3,
    "C": 5,
    "D": 8,
    "E": 13,
    "F": 20,
    "G": 32,
    "H": 50,
    "J": 80,
    "K": 125,
    "L": 200,
    "M": 315,
    "N": 500,
    "P": 800,
    "Q": 1250,
    "R": 2000,
}
AQL_VALUES: Final[tuple[float, ...]] = (
    0.010,
    0.015,
    0.025,
    0.040,
    0.065,
    0.10,
    0.15,
    0.25,
    0.40,
    0.65,
    1.0,
    1.5,
    2.5,
    4.0,
    6.5,
    10.0,
)
LEVELS: Final[tuple[InspectionLevel, ...]] = ("S-1", "S-2", "S-3", "S-4", "I", "II", "III")

# (lot upper bound inclusive, letters for S-1, S-2, S-3, S-4, I, II, III)
_TABLE_1: Final[tuple[tuple[int | None, str], ...]] = (
    (8, "AAAAAAB"),
    (15, "AAAAABC"),
    (25, "AABBBCD"),
    (50, "ABBCCDE"),
    (90, "BBCCCEF"),
    (150, "BBCDDFG"),
    (280, "BCDEEGH"),
    (500, "BCDEFHJ"),
    (1200, "CCEFGJK"),
    (3200, "CDEGHKL"),
    (10000, "CDFGJLM"),
    (35000, "CDFHKMN"),
    (150000, "DEGJLNP"),
    (500000, "DEGJMPQ"),
    (None, "DEHKNQR"),
)

# Diagonal index (letter index + AQL index) -> (Ac, Re); "down"/"up" are arrows.
_ZERO_DIAGONAL: Final = 14  # E (index 4) at AQL 1.0 (index 10) is Ac 0 / Re 1
_DIAGONAL: Final[tuple[tuple[int, int] | Literal["up", "down"], ...]] = (
    (0, 1),
    "up",
    "down",
    (1, 2),
    (2, 3),
    (3, 4),
    (5, 6),
    (7, 8),
    (10, 11),
    (14, 15),
    (21, 22),
)


@dataclass(frozen=True)
class SamplingPlan:
    lot_size: int
    aql: float
    inspection_level: InspectionLevel
    table_letter: str
    code_letter: str
    sample_size: int
    accept: int
    reject: int
    full_inspection: bool


def code_letter(lot_size: int, level: InspectionLevel) -> str:
    if lot_size < 2:
        raise ValueError(f"lot size must be >= 2, got {lot_size}")
    column = LEVELS.index(level)
    for upper, letters in _TABLE_1:
        if upper is None or lot_size <= upper:
            return letters[column]
    raise AssertionError("unreachable: Table 1 ends with an open range")


def _aql_index(aql: float) -> int:
    for index, value in enumerate(AQL_VALUES):
        if abs(value - aql) < 1e-9:
            return index
    raise ValueError(f"AQL {aql} is not a preferred ISO 2859-1 value in {AQL_VALUES}")


def _cell(letter_index: int, aql_index: int) -> tuple[int, int] | Literal["up", "down"]:
    offset = letter_index + aql_index - _ZERO_DIAGONAL
    if offset < 0:
        return "down"
    if offset >= len(_DIAGONAL):
        return "up"
    return _DIAGONAL[offset]


def _resolve(letter_index: int, aql_index: int) -> tuple[int, tuple[int, int]]:
    cell = _cell(letter_index, aql_index)
    if not isinstance(cell, str):
        return letter_index, cell
    step = 1 if cell == "down" else -1
    for direction in (step, -step):
        index = letter_index + direction
        while 0 <= index < len(CODE_LETTERS):
            candidate = _cell(index, aql_index)
            if not isinstance(candidate, str):
                return index, candidate
            index += direction
    raise AssertionError(f"no sampling plan in AQL column {AQL_VALUES[aql_index]}")


def sampling_plan(lot_size: int, aql: float, level: InspectionLevel = "II") -> SamplingPlan:
    letter = code_letter(lot_size, level)
    resolved, (accept, reject) = _resolve(CODE_LETTERS.index(letter), _aql_index(aql))
    plan_letter = CODE_LETTERS[resolved]
    sample_size = SAMPLE_SIZES[plan_letter]
    full = sample_size >= lot_size
    return SamplingPlan(
        lot_size=lot_size,
        aql=aql,
        inspection_level=level,
        table_letter=letter,
        code_letter=plan_letter,
        sample_size=lot_size if full else sample_size,
        accept=0 if full else accept,
        reject=1 if full else reject,
        full_inspection=full,
    )
