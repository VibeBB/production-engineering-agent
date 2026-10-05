from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from prodeng.cli import main

EXAMPLE_DIR = Path(__file__).parents[1] / "examples" / "smart-kettle"


def _copy_example(tmp_path: Path, *, fail_gates: bool = False) -> Path:
    (tmp_path / "upstream").mkdir(parents=True)
    shutil.copyfile(
        EXAMPLE_DIR / "upstream" / "smart-kettle.circuit-brief.json",
        tmp_path / "upstream" / "smart-kettle.circuit-brief.json",
    )
    payload = json.loads((EXAMPLE_DIR / "smart-kettle.prodeng.json").read_text(encoding="utf-8"))
    if fail_gates:
        payload["operations"][0]["cycle_time_s"] = 1000
    contract_path = tmp_path / "smart-kettle.prodeng.json"
    contract_path.write_text(json.dumps(payload), encoding="utf-8")
    return contract_path


def test_cli_success_and_exit_codes(tmp_path: Path) -> None:
    contract = _copy_example(tmp_path)
    assert main(["doctor"]) == 0
    assert main(["validate", str(contract)]) == 0
    assert (
        main(
            [
                "import",
                str(contract),
                "--from",
                "circuit-brief",
                str(contract.parent / "upstream" / "smart-kettle.circuit-brief.json"),
            ]
        )
        == 0
    )
    assert main(["gates", str(contract), "--json"]) == 0
    assert main(["export", str(contract), "--out", str(tmp_path / "export")]) == 0
    assert main(["author", str(contract), "--out", str(tmp_path / "author")]) == 0
    assert main(["requests", str(contract), "--out", str(tmp_path / "requests")]) == 0
    assert main(["liaison", str(tmp_path / "requests")]) == 0
    assert main(["sample", "--lot", "1000", "--aql", "1.0", "--level", "II"]) == 0


def test_cli_invalid_input_and_gate_failure_exit_codes(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{", encoding="utf-8")
    assert main(["validate", str(invalid)]) == 2
    contract = _copy_example(tmp_path / "valid")
    assert main(["author", str(contract)]) == 0
    failing = _copy_example(tmp_path / "failing", fail_gates=True)
    assert main(["author", str(failing)]) == 1
    assert main(["sample", "--lot", "1", "--aql", "1.0"]) == 2


def test_cli_record_impression_status_and_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("OPENHANDS_PROJECT_DIR", str(tmp_path))
    output = tmp_path / "out"
    output.mkdir()
    (output / "control-plan.csv").write_text("operation,check\n", encoding="utf-8")
    renders = output / "renders"
    renders.mkdir()
    (renders / "control-plan.png").write_bytes(b"png")
    impression = (
        "The inspection sequence follows the control plan and gives each operation "
        "a clear check. The sampled characteristics are tied to the listed process "
        "risks, so an inspector can identify the intended method. The remaining "
        "concern is that operator time has not yet been measured at production rate. "
        "Confirm the station timing during the pilot and update the plan if the "
        "observed cycle exceeds takt. Verify the sampling instructions at the work "
        "station before release so operators can follow the same sequence on every shift."
    )
    record_json = tmp_path / "record.json"
    record_json.write_text(
        json.dumps(
            {
                "stage": "projections",
                "artifacts": ["out/control-plan.csv"],
                "impression": impression,
            }
        ),
        encoding="utf-8",
    )

    assert main(["record", "impression", "--json", str(record_json)]) == 0
    written = json.loads(capsys.readouterr().out)
    assert written["verdict"] == "pass"
    assert written["record"]["stage"] == "projections"

    record_json.write_text(
        json.dumps(
            {
                "id": "inspection-method",
                "stage": "projections",
                "question": "Which inspection method should verify the process characteristic?",
                "principles": ["Inspection needs to detect process drift before shipment."],
                "options": [
                    {
                        "name": "attribute",
                        "pros": ["The check is quick to train."],
                        "cons": ["It provides limited measurement detail."],
                    },
                    {
                        "name": "variable",
                        "pros": ["The measurement reveals process variation."],
                        "cons": ["The station requires a calibrated instrument."],
                    },
                ],
                "chosen": "variable",
                "rationale": (
                    "A variable measurement provides process data before shipment and can "
                    "reveal drift early. The station already has a calibrated instrument, "
                    "so the added check fits the current process with a manageable burden."
                    " Keeping the recorded values will also help distinguish gradual wear "
                    "from an abrupt setup error during the pilot."
                ),
                "risks": ["The sampling rate may miss a short-lived process shift."],
                "revisit_when": "A capability study shows the process is stable.",
                "evidence": [{"path": "out/control-plan.csv"}],
            }
        ),
        encoding="utf-8",
    )
    assert main(["record", "decision", "--json", str(record_json)]) == 0
    assert json.loads(capsys.readouterr().out)["record"]["kind"] == "decision"

    record_json.write_text(
        json.dumps(
            {
                "image_path": "out/renders/control-plan.png",
                "model": "openhands/kimi-k3",
                "checklist": "control-plan",
                "findings": [],
                "impression": impression,
            }
        ),
        encoding="utf-8",
    )
    assert main(["record", "vision-review", "--json", str(record_json)]) == 0
    assert json.loads(capsys.readouterr().out)["record"]["kind"] == "vision_review"

    assert main(["record", "status"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["counts"]["stage_impression"] == 1
    assert status["counts"]["decision"] == 1
    assert status["counts"]["vision_review"] == 1

    record_json.write_text("{}", encoding="utf-8")
    assert main(["record", "impression", "--json", str(record_json)]) == 2
