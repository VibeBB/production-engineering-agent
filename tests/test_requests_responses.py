from __future__ import annotations

import json
from pathlib import Path

import pytest

from prodeng.contract import ProdengContract, load_contract
from prodeng.gates import run_gates
from prodeng.records import sha256_file
from prodeng.requests import (
    TARGET_AGENTS,
    RequestInput,
    TargetAgent,
    build_request,
    derive_requests,
    write_request,
)
from prodeng.responses import ProdengResponse, ResponseArtifact, ResponseStatus, liaison_status

EXAMPLE = Path(__file__).parents[1] / "examples" / "smart-kettle" / "smart-kettle.prodeng.json"
REQUEST_INPUTS = [RequestInput(path=EXAMPLE.name, sha256=sha256_file(EXAMPLE))]


def test_target_agents_match_supported_sibling_names() -> None:
    assert set(TARGET_AGENTS) == {
        "bard",
        "circuit",
        "dashboard",
        "doc",
        "firmware",
        "fpga",
        "mech",
        "sim",
        "wire",
        "ux",
    }


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
    requests = derive_requests(contract, gates, REQUEST_INPUTS)
    topics = {(request.target_agent, request.topic) for request in requests}
    assert topics == {
        ("firmware", "factory-test-mode"),
        ("circuit", "test-access"),
        ("mech", "fixtures"),
        ("wire", "harness-test"),
        ("doc", "work-instructions"),
    }
    high_risk = [request for request in requests if request.risk == "high"]
    declared = {
        item.id for item in contract.characteristics + contract.requirements + contract.inspections
    }
    assert all(request.cites and set(request.cites) <= declared for request in high_risk)
    assert all(request.model_dump()["schema_version"] == 2 for request in requests)
    assert all(request.inputs == REQUEST_INPUTS for request in requests)
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
            inputs=REQUEST_INPUTS,
        )


def test_factory_test_request_normalizes_terminal_periods() -> None:
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    ftm = payload["factory_test_mode"]
    ftm["entry"]["detail"] += "."
    ftm["entry"]["conditions"] = [f"{condition}." for condition in ftm["entry"]["conditions"]]
    ftm["field_lockout"]["detail"] += "."
    ftm["commands"][0]["request"] += "."
    ftm["commands"][0]["response_pattern"] += "."
    ftm["provisioning"][0]["source"] += "."
    ftm["exit"] += "."
    ftm["interface"]["nets"] = [f"{net}." for net in ftm["interface"]["nets"]]
    contract = ProdengContract.model_validate(payload)
    gates = run_gates(contract, EXAMPLE.parent)
    requests = derive_requests(contract, gates, REQUEST_INPUTS)
    firmware = next(
        request
        for request in requests
        if request.target_agent == "firmware" and request.topic == "factory-test-mode"
    )
    circuit = next(
        request
        for request in requests
        if request.target_agent == "circuit" and request.topic == "test-access"
    )
    assert firmware.requested_changes[0].endswith("boot timeout.")
    assert firmware.requested_changes[1].endswith("factory entry.")
    assert firmware.requested_changes[3] == (
        "TC-01: TEST SENSORS -> SENSORS PASS (timeout 2000 ms)"
    )
    assert firmware.requested_changes[5] == (
        "Provision serial_number from MES-issued unit serial; write_once=true."
    )
    assert firmware.requested_changes[-2].endswith("power-cycle; confirm normal firmware boot.")
    assert circuit.requested_changes[0] == (
        "Provide test access for nets: FTM_STRAP, UART_RX, UART_TX"
    )
    assert all(
        ".." not in change and ".;" not in change
        for change in firmware.requested_changes + circuit.requested_changes
    )


def test_liaison_open_answered_mismatched_orphan_and_malformed(tmp_path: Path) -> None:
    target: TargetAgent = "firmware"
    request = build_request(
        load_contract(EXAMPLE),
        target_agent=target,
        topic="test",
        risk="low",
        rationale="Coordinate implementation.",
        cites=[],
        requested_changes=["Review the interface."],
        inputs=REQUEST_INPUTS,
    )
    write_request(request, tmp_path, "open")
    write_request(request, tmp_path, "answered")
    write_request(request, tmp_path, "mismatched")
    write_request(request, tmp_path, "stale")
    responses: list[tuple[str, ResponseStatus, TargetAgent]] = [
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
            artifacts=[
                ResponseArtifact(
                    path="out/control-plan.csv",
                    sha256="a" * 64,
                )
            ],
            input_hashes={item.path: item.sha256 for item in request.inputs},
            decision_refs=["b" * 64],
        )
        (tmp_path / f"{stem}.prodeng-response.json").write_text(
            json.dumps(response.model_dump(mode="json")), encoding="utf-8"
        )
    stale_response = ProdengResponse(
        request="stale.prodeng-request.json",
        responder=target,
        status="accepted",
        reason="response uses outdated contract inputs",
        input_hashes={EXAMPLE.name: "0" * 64},
    )
    (tmp_path / "stale.prodeng-response.json").write_text(
        json.dumps(stale_response.model_dump(mode="json")), encoding="utf-8"
    )
    (tmp_path / "bad.prodeng-response.json").write_text("{", encoding="utf-8")
    liaison = liaison_status(tmp_path)
    states = {entry.request: entry.state for entry in liaison.entries}
    assert states == {
        "answered": "answered",
        "mismatched": "mismatched",
        "open": "open",
        "stale": "stale",
    }
    assert liaison.orphans == [str(tmp_path / "orphan.prodeng-response.json")]
    assert liaison.malformed == [str(tmp_path / "bad.prodeng-response.json")]
