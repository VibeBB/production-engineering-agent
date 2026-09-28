from __future__ import annotations

import hashlib
import json
from pathlib import Path

from prodeng.contract import ProdengContract
from prodeng.imports import ImportKind, import_source

FIXTURES = Path(__file__).parent / "fixtures" / "upstream"
EXAMPLE = Path(__file__).parents[1] / "examples" / "smart-kettle" / "smart-kettle.prodeng.json"


def _contract() -> ProdengContract:
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    payload["imports"] = []
    return ProdengContract.model_validate(payload)


def test_real_sibling_fixtures_extract_provenance() -> None:
    cases: list[tuple[ImportKind, str, str, str, str]] = [
        ("circuit-brief", "brief_led_loop.json", "circuit", "nets", "VIN"),
        ("circuit-connectivity", "board.connectivity.json", "circuit", "connectors", "J1"),
        ("mech-envelope", "housing.envelope.json", "mech", "anchors", "clip-01"),
        ("wire-contract", "sensor-harness.contract.json", "wire", "connectors", "C1"),
        ("ux-contract", "smart-kettle.ux.json", "ux", "surfaces", "kettle_body"),
    ]
    contract = _contract()
    for kind, filename, system, field, expected in cases:
        source = FIXTURES / filename
        contract = import_source(contract, kind, source, contract_dir=FIXTURES)
        imported = contract.imports[-1]
        assert imported.system == system
        assert imported.kind == kind
        assert expected in getattr(imported.extracted, field)
        assert imported.sha256 == hashlib.sha256(source.read_bytes()).hexdigest()


def test_reimport_replaces_same_system_and_path(tmp_path: Path) -> None:
    source = tmp_path / "brief.json"
    source.write_text(
        json.dumps({"nets": [{"name": "NET_A"}], "parts": [], "board": {}}),
        encoding="utf-8",
    )
    contract = import_source(_contract(), "circuit-brief", source, contract_dir=tmp_path)
    original_sha = contract.imports[0].sha256
    source.write_text(
        json.dumps({"nets": [{"name": "NET_B"}], "parts": [], "board": {}}),
        encoding="utf-8",
    )
    replacement = import_source(contract, "circuit-brief", source, contract_dir=tmp_path)
    assert len(replacement.imports) == 1
    assert replacement.imports[0].sha256 != original_sha
    assert replacement.imports[0].extracted.nets == ["NET_B"]
