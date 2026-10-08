"""Expose prodeng operations over a stdio MCP server."""

from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
from typing import Any, cast

from mcp import types
from mcp.server import Server
from mcp.server.lowlevel import NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

from . import __version__
from ._pillow import render_unavailable_reason
from .contract import contract_json, load_contract
from .doctor import run_doctor
from .gates import run_gates
from .imports import ImportKind, import_source
from .projections import write_projections
from .records import (
    DecisionInput,
    StageImpressionInput,
    VisionReviewInput,
    record_decision,
    record_impression,
    record_vision_review,
    records_summary,
)
from .report import write_report
from .requests import write_requests
from .responses import liaison_status
from .sampling import LEVELS, sampling_plan
from .ux_liaison import UxRespondInput, ux_inbox, ux_respond
from .workspace import workspace_path

server = Server(f"prodeng-mcp/{__version__}")

_SCHEMAS: dict[str, dict[str, Any]] = {
    "prodeng_record_decision": DecisionInput.model_json_schema(),
    "prodeng_record_impression": StageImpressionInput.model_json_schema(),
    "prodeng_record_vision_review": VisionReviewInput.model_json_schema(),
    "prodeng_records_status": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
    "prodeng_ux_inbox": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
    "prodeng_ux_respond": UxRespondInput.model_json_schema(),
    "prodeng_doctor": {"type": "object", "properties": {}, "additionalProperties": False},
    "prodeng_validate": {
        "type": "object",
        "properties": {"contract_path": {"type": "string"}},
        "required": ["contract_path"],
        "additionalProperties": False,
    },
    "prodeng_gates": {
        "type": "object",
        "properties": {"contract_path": {"type": "string"}},
        "required": ["contract_path"],
        "additionalProperties": False,
    },
    "prodeng_export": {
        "type": "object",
        "properties": {
            "contract_path": {"type": "string"},
            "out_dir": {"type": "string"},
        },
        "required": ["contract_path"],
        "additionalProperties": False,
    },
    "prodeng_author": {
        "type": "object",
        "properties": {
            "contract_path": {"type": "string"},
            "out_dir": {"type": "string"},
            "render": {"type": "boolean", "default": True},
        },
        "required": ["contract_path"],
        "additionalProperties": False,
    },
    "prodeng_render": {
        "type": "object",
        "properties": {
            "contract_path": {"type": "string"},
            "out_dir": {"type": "string"},
        },
        "required": ["contract_path"],
        "additionalProperties": False,
    },
    "prodeng_import": {
        "type": "object",
        "properties": {
            "contract_path": {"type": "string"},
            "kind": {
                "type": "string",
                "enum": [
                    "circuit-brief",
                    "circuit-connectivity",
                    "mech-envelope",
                    "wire-contract",
                    "ux-contract",
                    "fpga-production",
                    "firmware-production",
                ],
            },
            "file": {"type": "string"},
        },
        "required": ["contract_path", "kind", "file"],
        "additionalProperties": False,
    },
    "prodeng_requests": {
        "type": "object",
        "properties": {
            "contract_path": {"type": "string"},
            "out_dir": {"type": "string"},
        },
        "required": ["contract_path"],
        "additionalProperties": False,
    },
    "prodeng_liaison": {
        "type": "object",
        "properties": {"directory": {"type": "string"}},
        "required": ["directory"],
        "additionalProperties": False,
    },
    "prodeng_sample": {
        "type": "object",
        "properties": {
            "lot": {"type": "integer"},
            "aql": {"type": "number"},
            "level": {"type": "string", "default": "II"},
        },
        "required": ["lot", "aql"],
        "additionalProperties": False,
    },
}
_TOOL_DESCRIPTIONS = {
    "prodeng_record_decision": (
        "Record a production-engineering decision with principles, options, rationale, "
        "evidence, assumptions, unknowns, risks, and a revisit trigger."
    ),
    "prodeng_record_impression": (
        "Record a 400+ character, 3+ sentence impression of a completed production stage, "
        "bound to its final artifacts."
    ),
    "prodeng_record_vision_review": (
        "Record a 400+ character review of an image, bound to its path or vision-event ID."
    ),
    "prodeng_records_status": (
        "Count production-engineering records and report the last Stop-hook verdict."
    ),
    "prodeng_ux_inbox": (
        "List valid UX-creator requests for prodeng and report new, stale, blocked, "
        "or answered state."
    ),
    "prodeng_ux_respond": (
        "Validate and atomically write a SHA-bound SLP v2 response to a UX-creator request."
    ),
    "prodeng_doctor": "Report package, Python, and locked tools-image diagnostics.",
    "prodeng_validate": "Validate a production-engineering contract and its cross-references.",
    "prodeng_gates": "Evaluate deterministic gates for a production-engineering contract.",
    "prodeng_export": "Write deterministic manufacturing-plan projections for a contract.",
    "prodeng_author": (
        "Validate, gate, project, report, and derive requests; render sheets by default."
    ),
    "prodeng_render": (
        "Render deterministic production sheets as PNGs and return them inline for vision review."
    ),
    "prodeng_import": "Import a supported sibling artifact and record its SHA-256 provenance.",
    "prodeng_requests": "Derive and write structured change requests to sibling agents.",
    "prodeng_liaison": "Reconcile production-engineering requests with sibling responses.",
    "prodeng_sample": "Select an attribute sampling plan for a lot, AQL, and inspection level.",
}
_WRITE_TOOLS = {
    "prodeng_record_decision",
    "prodeng_record_impression",
    "prodeng_record_vision_review",
    "prodeng_ux_respond",
    "prodeng_export",
    "prodeng_author",
    "prodeng_render",
    "prodeng_import",
    "prodeng_requests",
}


def tool_specs() -> list[types.Tool]:
    return [
        types.Tool(
            name=name,
            description=_TOOL_DESCRIPTIONS[name],
            inputSchema=schema,
            annotations=types.ToolAnnotations(
                title=name,
                readOnlyHint=name not in _WRITE_TOOLS,
                destructiveHint=False,
                idempotentHint=True,
                openWorldHint=False,
            ),
        )
        for name, schema in _SCHEMAS.items()
    ]


def _default_out(contract_path: Path, product_name: str) -> Path:
    return contract_path.parent / "out" / product_name


def image_content(path: Path) -> types.ImageContent | None:
    if path.suffix.lower() != ".png" or not path.is_file():
        return None
    return types.ImageContent(
        type="image",
        data=base64.b64encode(path.read_bytes()).decode("ascii"),
        mimeType="image/png",
    )


def _workspace_arguments(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    schema = _SCHEMAS.get(name)
    required_paths: set[str] = set()
    if schema is not None:
        required = schema.get("required", [])
        if isinstance(required, list):
            required_paths = {key for key in cast(list[Any], required) if isinstance(key, str)}

    normalized = dict(arguments)
    for key, value in arguments.items():
        if key not in {"path", "paths", "file", "directory"} and not key.endswith(
            ("_path", "_dir")
        ):
            continue
        if isinstance(value, list):
            values = cast(list[Any], value)
            normalized[key] = [
                _workspace_path_argument(key, item, required_paths) for item in values
            ]
        else:
            normalized[key] = _workspace_path_argument(key, value, required_paths)
    return normalized


def _workspace_path_argument(key: str, value: Any, required_paths: set[str]) -> Any:
    if value is None:
        if key in required_paths:
            raise ValueError(f"'{key}' must be a non-empty path")
        return None
    if not isinstance(value, str):
        raise ValueError(f"'{key}' must be a path string")
    if not value:
        if key in required_paths:
            raise ValueError(f"'{key}' must be a non-empty path")
        return value
    return str(workspace_path(value))


async def dispatch_tool(name: str, arguments: dict[str, Any]) -> dict[str, object]:
    if name == "prodeng_doctor":
        return run_doctor()
    if name == "prodeng_record_decision":
        return record_decision(arguments)
    if name == "prodeng_record_impression":
        return record_impression(arguments)
    if name == "prodeng_record_vision_review":
        return record_vision_review(arguments)
    if name == "prodeng_records_status":
        return records_summary()
    if name == "prodeng_ux_inbox":
        return ux_inbox()
    if name == "prodeng_ux_respond":
        return ux_respond(arguments)
    if name == "prodeng_liaison":
        status = liaison_status(Path(arguments["directory"]))
        return {"verdict": "pass", "stage": "liaison", **status.model_dump(mode="json")}
    if name == "prodeng_sample":
        level = arguments.get("level", "II")
        if level not in LEVELS:
            raise ValueError(f"level must be one of {LEVELS}")
        plan = sampling_plan(
            arguments["lot"],
            arguments["aql"],
            level,
        )
        return {"verdict": "pass", **plan.__dict__}

    contract_path = Path(arguments["contract_path"])
    contract = load_contract(contract_path)
    if name == "prodeng_validate":
        return {
            "verdict": "pass",
            "stage": "validate",
            "contract": str(contract_path),
            "product": contract.product.name,
        }
    if name == "prodeng_gates":
        return run_gates(contract, contract_path.parent).to_dict(contract)
    if name == "prodeng_import":
        updated = import_source(
            contract,
            cast(ImportKind, arguments["kind"]),
            Path(arguments["file"]),
            contract_dir=contract_path.parent,
        )
        contract_path.write_text(contract_json(updated), encoding="utf-8")
        return {
            "verdict": "pass",
            "imports": [item.model_dump(mode="json") for item in updated.imports],
        }
    if name in ("prodeng_export", "prodeng_author"):
        render_enabled = name == "prodeng_author" and arguments.get("render", True)
        if not isinstance(render_enabled, bool):
            raise ValueError("'render' must be a boolean")
        out_dir = (
            Path(arguments["out_dir"])
            if arguments.get("out_dir")
            else _default_out(contract_path, contract.product.name)
        )
        paths = write_projections(contract, contract_path.stem.removesuffix(".prodeng"), out_dir)
        payload: dict[str, object] = {
            "verdict": "pass",
            "stage": "export",
            "written": {key: str(path) for key, path in paths.items()},
        }
        if name == "prodeng_author":
            gates = run_gates(contract, contract_path.parent)
            request_paths = write_requests(contract, gates, contract_path.parent, contract_path)
            render_paths: dict[str, Path] = {}
            render_skipped: str | None = None
            if render_enabled:
                render_skipped = render_unavailable_reason()
                if render_skipped is None:
                    from .render import render_sheets

                    render_paths = render_sheets(contract, out_dir)
            # Report written after renders so vision_points can list the sheets.
            paths.update(write_report(contract, gates, out_dir, contract_path.parent))
            payload = {
                **gates.to_dict(contract),
                "stage": "author",
                "written": {key: str(path) for key, path in paths.items()},
                "requests": [str(path) for path in request_paths],
            }
            if render_enabled:
                if render_skipped is not None:
                    payload["render_skipped"] = render_skipped
                else:
                    payload.update(
                        {
                            "vision_review_required": [str(path) for path in render_paths.values()],
                            "next_step": (
                                "Look at every image and record prodeng_record_vision_review "
                                "for each (400+ character impression judging accuracy, "
                                "ambiguity, design intent and whether the shop floor could act "
                                "on it)."
                            ),
                        }
                    )
        return payload
    if name == "prodeng_render":
        render_unavailable = render_unavailable_reason()
        if render_unavailable is not None:
            raise ValueError(render_unavailable)
        from .render import render_sheets

        out_dir = (
            Path(arguments["out_dir"])
            if arguments.get("out_dir")
            else _default_out(contract_path, contract.product.name)
        )
        paths = render_sheets(contract, out_dir)
        return {
            "verdict": "pass",
            "stage": "render",
            "vision_review_required": [str(path) for path in paths.values()],
            "next_step": (
                "Look at every image and record prodeng_record_vision_review for each "
                "(400+ character impression judging accuracy, ambiguity, design intent "
                "and whether the shop floor could act on it)."
            ),
        }
    if name == "prodeng_requests":
        gates = run_gates(contract, contract_path.parent)
        out_dir = Path(arguments["out_dir"]) if arguments.get("out_dir") else contract_path.parent
        return {
            "verdict": "pass",
            "stage": "requests",
            "written": [
                str(path) for path in write_requests(contract, gates, out_dir, contract_path)
            ],
        }
    return {"verdict": "fail", "detail": f"unknown tool {name}"}


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return tool_specs()


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> types.CallToolResult:
    is_error = name not in _SCHEMAS
    if is_error:
        payload: object = {"verdict": "fail", "detail": f"unknown tool {name}"}
    else:
        try:
            payload = await dispatch_tool(name, _workspace_arguments(name, arguments or {}))
        except Exception as exc:
            payload = {"verdict": "fail", "detail": f"{name} error: {exc}"}
            is_error = True
    content: list[types.ContentBlock] = [
        types.TextContent(type="text", text=json.dumps(payload, indent=2, sort_keys=True))
    ]
    if not is_error:
        image_paths = payload.get("vision_review_required")
        if isinstance(image_paths, list):
            for image_path in cast(list[object], image_paths):
                if isinstance(image_path, str):
                    image = image_content(Path(image_path))
                    if image is not None:
                        content.append(image)
    return types.CallToolResult(
        content=content,
        isError=is_error,
    )


async def _run() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name=f"prodeng-mcp/{__version__}",
                server_version=__version__,
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
