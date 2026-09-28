from __future__ import annotations

import json
import shutil
from pathlib import Path

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
