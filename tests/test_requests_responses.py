from __future__ import annotations

import json
from pathlib import Path

import pytest

from prodeng.contract import ProdengContract, load_contract
from prodeng.gates import run_gates
from prodeng.requests import build_request, derive_requests, write_request
from prodeng.responses import ProdengResponse, ResponseStatus, liaison_status

EXAMPLE = Path(__file__).parents[1] / "examples" / "smart-kettle" / "smart-kettle.prodeng.json"


def test_derives_each_of_five_sibling_request_rules(tmp_path: Path) -> None:
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    payload["operations"].append(
        {
            "id": "OP07",
            "name": "Harness continuity inspection",
            "kind": "harness",
            "station": "WIRE",
            "cycle_time_s": 10,
            "operators": 1,
            "tools": ["continuity tester"],
            "fixtures": [],
            "esd_sensitive": False,
            "safety_hazards": [],
            "safety_precautions": [],
            "work_elements": [
                {
                    "step": "Verify harness pin-to-pin continuity.",
                    "key_points": ["Compare every conductor with the approved wiring table."],
                    "reasons": ["Prevents miswiring from reaching final assembly."],
                }
            ],
        }
    )
    contract = ProdengContract.model_validate(payload)
    gates = run_gates(contract, EXAMPLE.parent)
    requests = derive_requests(contract, gates)
    topics = {(request.target_agent, request.topic) for request in requests}
    assert topics == {
        ("firmware", "factory-test-mode"),
        ("circuit", "test-access"),
        ("mech", "fixtures"),
        ("wire", "harness-test"),
        ("document", "work-instructions"),
    }
    high_risk = [request for request in requests if request.risk == "high"]
    declared = {
        item.id for item in contract.characteristics + contract.requirements + contract.inspections
    }
    assert all(request.cites and set(request.cites) <= declared for request in high_risk)
    assert all(request.model_dump()["schema_version"] == 1 for request in requests)
    assert all(
        write_request(request, tmp_path, request.topic).suffix == ".json" for request in requests
    )


def test_high_risk_request_requires_a_declared_citation() -> None:
    contract = load_contract(EXAMPLE)
    with pytest.raises(ValueError, match="high-risk requests"):
        build_request(
            contract,
            target_agent="firmware",
            topic="factory-test-mode",
            risk="high",
            rationale="Add the guarded factory mode.",
            cites=[],
            requested_changes=["Implement guarded entry."],
        )


def test_liaison_open_answered_mismatched_orphan_and_malformed(tmp_path: Path) -> None:
    target = "firmware"
    request = build_request(
        load_contract(EXAMPLE),
        target_agent=target,
        topic="test",
        risk="low",
        rationale="Coordinate implementation.",
        cites=[],
        requested_changes=["Review the interface."],
    )
    write_request(request, tmp_path, "open")
    write_request(request, tmp_path, "answered")
    write_request(request, tmp_path, "mismatched")
    responses: list[tuple[str, ResponseStatus, str]] = [
        ("answered", "accepted", target),
        ("mismatched", "rejected", "bard"),
        ("orphan", "accepted", target),
    ]
    for stem, status, responder in responses:
        response = ProdengResponse(
            request=f"{stem}.prodeng-request.json",
            responder=responder,
            status=status,
            reason="review complete",
        )
        (tmp_path / f"{stem}.prodeng-response.json").write_text(
            json.dumps(response.model_dump(mode="json")), encoding="utf-8"
        )
    (tmp_path / "bad.prodeng-response.json").write_text("{", encoding="utf-8")
    liaison = liaison_status(tmp_path)
    states = {entry.request: entry.state for entry in liaison.entries}
    assert states == {"answered": "answered", "mismatched": "mismatched", "open": "open"}
    assert liaison.orphans == [str(tmp_path / "orphan.prodeng-response.json")]
    assert liaison.malformed == [str(tmp_path / "bad.prodeng-response.json")]
