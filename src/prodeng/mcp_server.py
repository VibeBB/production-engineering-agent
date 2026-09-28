"""Expose prodeng operations over a stdio MCP server."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, cast

from mcp import types
from mcp.server import Server
from mcp.server.lowlevel import NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

from . import __version__
from .contract import contract_json, load_contract
from .doctor import run_doctor
from .gates import run_gates
from .imports import ImportKind, import_source
from .projections import write_projections
from .report import write_report
from .requests import write_requests
from .responses import liaison_status
from .sampling import LEVELS, sampling_plan

server = Server(f"prodeng-mcp/{__version__}")

_SCHEMAS: dict[str, dict[str, Any]] = {
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
    "prodeng_doctor": "Report package, Python, and locked tools-image diagnostics.",
    "prodeng_validate": "Validate a production-engineering contract and its cross-references.",
    "prodeng_gates": "Evaluate deterministic gates for a production-engineering contract.",
    "prodeng_export": "Write deterministic manufacturing-plan projections for a contract.",
    "prodeng_author": "Validate, gate, project, report, and derive requests for a contract.",
    "prodeng_import": "Import a supported sibling artifact and record its SHA-256 provenance.",
    "prodeng_requests": "Derive and write structured change requests to sibling agents.",
    "prodeng_liaison": "Reconcile production-engineering requests with sibling responses.",
    "prodeng_sample": "Select an attribute sampling plan for a lot, AQL, and inspection level.",
}
_WRITE_TOOLS = {
    "prodeng_export",
    "prodeng_author",
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


async def dispatch_tool(name: str, arguments: dict[str, Any]) -> dict[str, object]:
    if name == "prodeng_doctor":
        return run_doctor()
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
            request_paths = write_requests(contract, gates, contract_path.parent)
            paths.update(write_report(contract, gates, out_dir, contract_path.parent))
            payload = {
                **gates.to_dict(contract),
                "stage": "author",
                "written": {key: str(path) for key, path in paths.items()},
                "requests": [str(path) for path in request_paths],
            }
        return payload
    if name == "prodeng_requests":
        gates = run_gates(contract, contract_path.parent)
        out_dir = Path(arguments["out_dir"]) if arguments.get("out_dir") else contract_path.parent
        return {
            "verdict": "pass",
            "stage": "requests",
            "written": [str(path) for path in write_requests(contract, gates, out_dir)],
        }
    return {"verdict": "fail", "detail": f"unknown tool {name}"}


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return tool_specs()


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.ContentBlock]:
    try:
        payload: object = await dispatch_tool(name, arguments or {})
    except Exception as exc:
        payload = {"verdict": "fail", "detail": f"{name} error: {exc}"}
    return [types.TextContent(type="text", text=json.dumps(payload, indent=2, sort_keys=True))]


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
