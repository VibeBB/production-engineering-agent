from __future__ import annotations

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
