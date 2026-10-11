"""Integrated product EBOM: one unit's parts from the pinned circuit, mech and wire sources."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

from .contract import ProdengContract

Line = dict[str, object]

LID_SCREWS = 4


def _objects(payload: dict[str, object], field: str) -> list[dict[str, object]]:
    value = payload.get(field, [])
    if not isinstance(value, list):
        raise ValueError(f"{field!r} must be a list")
    items = cast(list[object], value)
    if not all(isinstance(item, dict) for item in items):
        raise ValueError(f"{field!r} entries must be objects")
    return [cast(dict[str, object], item) for item in items]


def _text(item: dict[str, object], field: str) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field!r} must be a non-empty string")
    return value


def _line(
    system: str, item: str, description: str, quantity: float, unit: str, refs: list[str]
) -> Line:
    return {
        "system": system,
        "item": item,
        "description": description,
        "quantity": quantity,
        "unit": unit,
        "refs": sorted(refs),
    }


def _circuit_lines(payload: dict[str, object]) -> list[Line]:
    groups: dict[tuple[str, str, str], list[str]] = {}
    for part in _objects(payload, "parts"):
        value = part.get("value")
        key = (_text(part, "lib_id"), _text(part, "footprint"), str(value or ""))
        groups.setdefault(key, []).append(_text(part, "reference"))
    lines = [
        _line("circuit", lib_id, f"{footprint} {value}".strip(), len(refs), "pcs", refs)
        for (lib_id, footprint, value), refs in groups.items()
    ]
    if isinstance(payload.get("board"), dict):
        name = str(payload.get("name") or "board")
        lines.append(_line("circuit", f"pcb:{name}", "bare printed circuit board", 1, "pcs", []))
    return lines


def _mech_lines(payload: dict[str, object]) -> list[Line]:
    name, material = _text(payload, "name"), _text(payload, "material")
    described = f"{material}, {_text(payload, 'process')}"
    if payload.get("design_type") != "enclosure":
        return [_line("mech", name, described, 1, "pcs", [])]
    enclosure = payload.get("enclosure")
    if not isinstance(enclosure, dict):
        raise ValueError("enclosure brief declares no enclosure")
    spec = cast(dict[str, object], enclosure)
    lines = [
        _line("mech", f"{name}-base", described, 1, "pcs", []),
        _line("mech", f"{name}-lid", described, 1, "pcs", []),
    ]
    if spec.get("lid", "screw") == "screw":
        screw = spec.get("screw")
        if not isinstance(screw, dict):
            raise ValueError("screw lid declares no screw")
        size = _text(cast(dict[str, object], screw), "size")
        lines.append(_line("mech", f"screw:{size}", "lid corner screw", LID_SCREWS, "pcs", []))
    return lines


def _wire_lines(payload: dict[str, object]) -> list[Line]:
    housings: dict[str, list[str]] = {}
    cavity_terminal: dict[tuple[str, str], str] = {}
    for connector in _objects(payload, "connectors"):
        cid = _text(connector, "id")
        housing = connector.get("housing") or _text(connector, "family")
        housings.setdefault(str(housing), []).append(cid)
        for cavity in _objects(connector, "cavities"):
            terminal = cavity.get("terminal")
            if isinstance(terminal, str) and terminal:
                cavity_terminal[(cid, _text(cavity, "id"))] = terminal
    terminals: dict[str, list[str]] = {}
    lengths: dict[str, float] = {}
    for wire in _objects(payload, "wires"):
        wid = _text(wire, "id")
        length = wire.get("length_m")
        if isinstance(length, bool) or not isinstance(length, int | float) or length <= 0:
            raise ValueError(f"wire {wid} length_m must be a positive number")
        wire_type = _text(wire, "wire_type")
        lengths[wire_type] = lengths.get(wire_type, 0.0) + float(length)
        for end, declared in (("from_endpoint", "terminal_a"), ("to_endpoint", "terminal_b")):
            point = wire.get(end)
            name = wire.get(declared)
            if name is None and isinstance(point, dict):
                at = cast(dict[str, object], point)
                name = cavity_terminal.get((str(at.get("connector")), str(at.get("cavity"))))
            if isinstance(name, str) and name:
                terminals.setdefault(name, []).append(wid)
    names = {_text(t, "id"): _text(t, "name") for t in _objects(payload, "wire_types")}
    unknown_types = sorted(set(lengths) - set(names))
    if unknown_types:
        raise ValueError(f"wires use undeclared wire types: {', '.join(unknown_types)}")
    splices: dict[str, list[str]] = {}
    for splice in _objects(payload, "splices"):
        splices.setdefault(str(splice.get("kind") or "crimp"), []).append(_text(splice, "id"))
    return [
        *(_line("wire", h, "connector housing", len(c), "pcs", c) for h, c in housings.items()),
        *(_line("wire", t, "terminal", len(w), "pcs", w) for t, w in terminals.items()),
        *(
            _line("wire", wt, names[wt], round(length, 4), "m", [])
            for wt, length in lengths.items()
        ),
        *(_line("wire", f"splice:{k}", "splice", len(s), "pcs", s) for k, s in splices.items()),
    ]


_SOURCES: dict[str, Callable[[dict[str, object]], list[Line]]] = {
    "circuit-brief": _circuit_lines,
    "mech-brief": _mech_lines,
    "wire-contract": _wire_lines,
}


def product_ebom(contract: ProdengContract, contract_dir: Path) -> dict[str, object]:
    """One unit's EBOM from every declared ``ebom_sources`` import, re-read and hash-checked."""
    lines: list[Line] = []
    sources: list[dict[str, str]] = []
    unknown: list[str] = []
    failed: list[str] = []
    for kind in contract.ebom_sources:
        refs = [item for item in contract.imports if item.kind == kind]
        if len(refs) != 1:
            target = unknown if not refs else failed
            target.append(f"{kind}: {'not imported' if not refs else 'imported more than once'}")
            continue
        ref = refs[0]
        path = Path(ref.path) if Path(ref.path).is_absolute() else contract_dir / ref.path
        try:
            raw = path.read_bytes()
        except OSError as exc:
            unknown.append(f"{kind}: unreadable: {exc}")
            continue
        if hashlib.sha256(raw).hexdigest() != ref.sha256:
            failed.append(f"{kind}: changed since import")
            continue
        try:
            document: object = json.loads(raw)
            if not isinstance(document, dict):
                raise ValueError("artifact is not a JSON object")
            lines.extend(_SOURCES[kind](cast(dict[str, object], document)))
        except (ValueError, UnicodeDecodeError) as exc:
            failed.append(f"{kind}: malformed: {exc}")
            continue
        sources.append({"kind": kind, "path": ref.path, "sha256": ref.sha256})
    lines.sort(key=lambda line: (str(line["system"]), str(line["item"]), str(line["description"])))
    return {
        "artifact_kind": "prodeng_ebom",
        "schema_version": 1,
        "product": contract.product.name,
        "units": 1,
        "sources": sources,
        "lines": lines,
        "failed": failed,
        "unknown": unknown,
        "verdict": "fail" if failed else "unknown" if unknown else "pass",
    }
