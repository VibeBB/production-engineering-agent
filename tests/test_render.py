# pyright: reportPrivateUsage=false

from __future__ import annotations

import ast
import asyncio
import hashlib
import json
import shutil
from collections.abc import Coroutine
from pathlib import Path
from typing import Any, cast

import pytest
from mcp import types
from PIL import Image

from prodeng import mcp_server
from prodeng import render as render_module
from prodeng.contract import ProdengContract, load_contract
from prodeng.projections import write_projections
from prodeng.render import MAX_HEIGHT, RED, render_sheets

EXAMPLE = Path(__file__).parents[1] / "examples" / "smart-kettle"


def _contract_copy(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        EXAMPLE / "smart-kettle.prodeng.json",
        directory / "smart-kettle.prodeng.json",
    )
    shutil.copytree(EXAMPLE / "upstream", directory / "upstream")
    return directory / "smart-kettle.prodeng.json"


def _mcp_call(name: str, arguments: dict[str, Any]) -> types.CallToolResult:
    return asyncio.run(
        cast(Coroutine[Any, Any, types.CallToolResult], mcp_server.call_tool(name, arguments))
    )


def test_rendered_sheets_are_deterministic_and_index_hashes_sources(
    tmp_path: Path,
) -> None:
    contract = load_contract(EXAMPLE / "smart-kettle.prodeng.json")
    first = render_sheets(contract, tmp_path / "first")
    second = render_sheets(contract, tmp_path / "second")
    assert first.keys() == second.keys()
    assert all(first[name].read_bytes() == second[name].read_bytes() for name in first)
    assert all(path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n") for path in first.values())
    for path in first.values():
        with Image.open(path) as image:
            assert image.height <= MAX_HEIGHT

    index_path = tmp_path / "first" / "renders" / "index.json"
    assert index_path.read_bytes() == (tmp_path / "second" / "renders" / "index.json").read_bytes()
    index = json.loads(index_path.read_text(encoding="utf-8"))
    projections = write_projections(contract, "smart-kettle", tmp_path / "source")
    source_paths = {
        "control-plan.csv": projections["control_plan"],
        "pfmea.csv": projections["pfmea"],
        "line-balance.csv": projections["line_balance"],
        "work-instructions.md": projections["work_instructions"],
        "factory-test-spec.json": projections["factory_test_json"],
    }
    assert index["schema_version"] == 1
    assert index["product"] == "smart-kettle"
    assert isinstance(index["font"], str)
    assert index["font"]
    for item in index["renders"]:
        image_path = tmp_path / "first" / item["path"]
        assert hashlib.sha256(image_path.read_bytes()).hexdigest() == item["sha256"]
        assert (
            hashlib.sha256(source_paths[item["source"]].read_bytes()).hexdigest()
            == item["source_sha256"]
        )
    operation_count = len(contract.operations)
    assert sum(name.startswith("work-instruction-") for name in first) == operation_count
    assert "factory-test-spec" in first
    assert "line-balance" in first


def test_renderer_string_literals_are_ascii() -> None:
    source_path = Path(__file__).parents[1] / "src" / "prodeng" / "render.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    string_literals = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]

    assert all(value.isascii() for value in string_literals)


def test_nice_axis_ticks_have_readable_integer_labels() -> None:
    step, ticks = render_module._nice_axis_ticks(80.64)

    assert step in (10, 20)
    assert 4 <= len(ticks) <= 8
    assert ticks[-1] >= 80.64 * 1.05
    assert all(value.is_integer() for value in ticks)
    assert all(render_module._axis_tick_label(value, step).isdigit() for value in ticks)
    assert render_module._takt_utilization_label(32, 72) == "32 s (44%)"


def test_multivalue_cells_use_newlines_and_line_balance_summary() -> None:
    contract = load_contract(EXAMPLE / "smart-kettle.prodeng.json")
    ftm = contract.factory_test_mode
    assert ftm is not None

    conditions = next(row[2] for row in render_module._ftm_rows(contract) if row[1] == "Conditions")
    assert conditions.splitlines() == ftm.entry.conditions
    interface = next(row[2] for row in render_module._ftm_rows(contract) if row[0] == "Interface")
    assert interface.startswith(f"Settings: {ftm.interface.settings}\nNets:\n")
    assert interface.splitlines()[2:] == sorted(ftm.interface.nets)
    assert ".;" not in interface

    operation = contract.operations[0]
    element = operation.work_elements[0].model_copy(
        update={
            "key_points": ["First point.", "Second point."],
            "reasons": ["First reason.", "Second reason."],
        }
    )
    updated_operation = operation.model_copy(update={"work_elements": [element]})
    assert render_module._operation_rows(updated_operation)[0][1:] == (
        "First point.\nSecond point.",
        "First reason.\nSecond reason.",
    )

    controls = [contract.inspections[0].id, contract.inspections[1].id]
    failure_mode = contract.failure_modes[0].model_copy(update={"controls": controls})
    updated_contract = contract.model_copy(update={"failure_modes": [failure_mode]})
    assert render_module._pfmea_rows(updated_contract)[0][-1] == "\n".join(sorted(controls))

    efficiency_line, bottleneck_line = render_module._line_balance_summary(
        contract,
        render_module.line_balance_efficiency(contract),
    )
    assert efficiency_line == (
        "Balance efficiency 30.1% (sum of cycle times / (operations x takt))"
    )
    assert bottleneck_line == "Bottleneck OP04 - Mechanical assembly: 32 s (44% of takt 72 s)"


def test_line_balance_highlights_over_takt_operations(tmp_path: Path) -> None:
    payload = json.loads((EXAMPLE / "smart-kettle.prodeng.json").read_text(encoding="utf-8"))
    payload["operations"][0]["cycle_time_s"] = 1000
    contract = ProdengContract.model_validate(payload)
    images = render_sheets(contract, tmp_path)
    with Image.open(images["line-balance"]) as image:
        assert image.getpixel((370, 263)) == RED


def test_work_instruction_paginates_long_steps_and_caps_image_height(tmp_path: Path) -> None:
    contract = load_contract(EXAMPLE / "smart-kettle.prodeng.json")
    operation = contract.operations[0]
    element = operation.work_elements[0]
    long_operation = operation.model_copy(
        update={"work_elements": [element] * 190},
    )
    changed = contract.model_copy(
        update={
            "operations": [long_operation, *contract.operations[1:]],
        }
    )
    images = render_sheets(changed, tmp_path)
    pages = [
        path for name, path in images.items() if name.startswith(f"work-instruction-{operation.id}")
    ]
    assert len(pages) > 1
    for path in pages:
        with Image.open(path) as image:
            assert image.height <= MAX_HEIGHT


def test_render_tool_returns_inline_images_and_author_can_disable_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENHANDS_PROJECT_DIR", str(tmp_path))
    contract_path = _contract_copy(tmp_path / "workspace")
    render_result = _mcp_call(
        "prodeng_render",
        {"contract_path": str(contract_path), "out_dir": str(tmp_path / "render")},
    )
    assert render_result.isError is False
    assert isinstance(render_result.content[0], types.TextContent)
    render_payload = json.loads(render_result.content[0].text)
    image_blocks = [item for item in render_result.content if isinstance(item, types.ImageContent)]
    assert len(image_blocks) == len(render_payload["vision_review_required"])
    assert image_blocks
    assert all(item.mimeType == "image/png" for item in image_blocks)

    author_result = _mcp_call(
        "prodeng_author",
        {
            "contract_path": str(contract_path),
            "out_dir": str(tmp_path / "author"),
            "render": False,
        },
    )
    assert author_result.isError is False
    assert len(author_result.content) == 1
    assert isinstance(author_result.content[0], types.TextContent)
