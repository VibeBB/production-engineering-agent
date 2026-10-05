"""Command-line interface for the deterministic prodeng core."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast

from . import __version__
from ._pillow import render_unavailable_reason
from .contract import ProdengContract, contract_json, load_contract
from .doctor import run_doctor
from .gates import run_gates
from .imports import IMPORT_SYSTEMS, import_source
from .projections import write_projections
from .records import RECORDERS, records_summary
from .report import write_report
from .requests import write_requests
from .responses import liaison_status
from .sampling import LEVELS, sampling_plan
from .ux_liaison import ux_inbox, ux_respond


def _print(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _error(stage: str, exc: Exception) -> int:
    _print({"verdict": "fail", "stage": stage, "detail": str(exc)})
    return 2


def _out_dir(contract_path: Path, requested: str | None, contract: ProdengContract) -> Path:
    if requested:
        return Path(requested)
    return contract_path.parent / "out" / contract.product.name


def _load(args: argparse.Namespace) -> tuple[Path, ProdengContract]:
    contract_path = Path(args.contract)
    return contract_path, load_contract(contract_path)


def _cmd_doctor(_args: argparse.Namespace) -> int:
    _print(run_doctor())
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    try:
        contract_path, contract = _load(args)
    except (OSError, ValueError) as exc:
        return _error("validate", exc)
    _print(
        {
            "verdict": "pass",
            "stage": "validate",
            "contract": str(contract_path),
            "product": contract.product.name,
        }
    )
    return 0


def _cmd_gates(args: argparse.Namespace) -> int:
    try:
        contract_path, contract = _load(args)
        report = run_gates(contract, contract_path.parent)
    except (OSError, ValueError) as exc:
        return _error("gates", exc)
    if args.json:
        _print(report.to_dict(contract))
    else:
        print(f"{contract.product.name}: {report.verdict}")
        for check in report.checks:
            print(f"{check.status:7} {check.id} {check.subject}: {check.detail}")
    return 0 if report.verdict == "pass" else 1


def _cmd_export(args: argparse.Namespace) -> int:
    try:
        contract_path, contract = _load(args)
        out_dir = _out_dir(contract_path, args.out, contract)
        paths = write_projections(contract, contract_path.stem.removesuffix(".prodeng"), out_dir)
    except (OSError, ValueError) as exc:
        return _error("export", exc)
    _print({"verdict": "pass", "stage": "export", "written": {k: str(v) for k, v in paths.items()}})
    return 0


def _cmd_author(args: argparse.Namespace) -> int:
    try:
        contract_path, contract = _load(args)
        report = run_gates(contract, contract_path.parent)
        out_dir = _out_dir(contract_path, args.out, contract)
        paths = write_projections(contract, contract_path.stem.removesuffix(".prodeng"), out_dir)
        request_paths = write_requests(contract, report, contract_path.parent, contract_path)
        paths.update(write_report(contract, report, out_dir, contract_path.parent))
        render_paths: dict[str, Path] = {}
        render_skipped: str | None = None
        if args.render:
            render_skipped = render_unavailable_reason()
            if render_skipped is None:
                from .render import render_sheets

                render_paths = render_sheets(contract, out_dir)
    except (OSError, ValueError) as exc:
        return _error("author", exc)
    payload: dict[str, object] = {
        **report.to_dict(contract),
        "stage": "author",
        "written": {key: str(value) for key, value in paths.items()},
        "requests": [str(path) for path in request_paths],
    }
    if args.render:
        if render_skipped is not None:
            payload["render_skipped"] = render_skipped
        else:
            payload.update(
                {
                    "vision_review_required": [str(path) for path in render_paths.values()],
                    "next_step": (
                        "Look at every image and record prodeng_record_vision_review for each "
                        "(400+ character impression judging accuracy, ambiguity, design intent "
                        "and whether the shop floor could act on it)."
                    ),
                }
            )
    _print(payload)
    return 0 if report.verdict == "pass" else 1


def _cmd_render(args: argparse.Namespace) -> int:
    try:
        render_unavailable = render_unavailable_reason()
        if render_unavailable is not None:
            raise ValueError(render_unavailable)
        from .render import render_sheets

        contract_path, contract = _load(args)
        out_dir = _out_dir(contract_path, args.out, contract)
        paths = render_sheets(contract, out_dir)
    except (OSError, ValueError) as exc:
        return _error("render", exc)
    _print(
        {
            "verdict": "pass",
            "stage": "render",
            "rendered": {key: str(value) for key, value in paths.items()},
            "vision_review_required": [str(path) for path in paths.values()],
            "next_step": (
                "Look at every image and record prodeng_record_vision_review for each "
                "(400+ character impression judging accuracy, ambiguity, design intent "
                "and whether the shop floor could act on it)."
            ),
        }
    )
    return 0


def _cmd_import(args: argparse.Namespace) -> int:
    try:
        contract_path, contract = _load(args)
        updated = import_source(
            contract,
            args.kind,
            Path(args.file),
            contract_dir=contract_path.parent,
        )
        contract_path.write_text(contract_json(updated), encoding="utf-8")
    except (OSError, ValueError) as exc:
        return _error("import", exc)
    _print(
        {
            "verdict": "pass",
            "stage": "import",
            "contract": str(contract_path),
            "imports": [item.model_dump(mode="json") for item in updated.imports],
        }
    )
    return 0


def _cmd_requests(args: argparse.Namespace) -> int:
    try:
        contract_path, contract = _load(args)
        report = run_gates(contract, contract_path.parent)
        out_dir = Path(args.out) if args.out else contract_path.parent
        paths = write_requests(contract, report, out_dir, contract_path)
    except (OSError, ValueError) as exc:
        return _error("requests", exc)
    _print({"verdict": "pass", "stage": "requests", "written": [str(path) for path in paths]})
    return 0


def _cmd_liaison(args: argparse.Namespace) -> int:
    try:
        status = liaison_status(Path(args.directory))
    except (OSError, ValueError) as exc:
        return _error("liaison", exc)
    _print({"verdict": "pass", "stage": "liaison", **status.model_dump(mode="json")})
    return 0


def _cmd_ux_inbox(_args: argparse.Namespace) -> int:
    try:
        result = ux_inbox()
    except (OSError, ValueError) as exc:
        return _error("ux inbox", exc)
    _print(result)
    return 0 if result["verdict"] == "pass" else 2


def _cmd_ux_respond(args: argparse.Namespace) -> int:
    try:
        raw = json.loads(Path(args.json).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("response JSON must be an object")
        result = ux_respond(cast(dict[str, object], raw))
    except (OSError, ValueError) as exc:
        return _error("ux respond", exc)
    _print(result)
    return 0 if result["verdict"] == "pass" else 2


def _cmd_sample(args: argparse.Namespace) -> int:
    try:
        if args.level not in LEVELS:
            raise ValueError(f"level must be one of {LEVELS}")
        plan = sampling_plan(args.lot, args.aql, args.level)
    except ValueError as exc:
        return _error("sample", exc)
    _print({"verdict": "pass", **plan.__dict__})
    return 0


def _cmd_record(args: argparse.Namespace) -> int:
    if args.kind == "status":
        _print(records_summary())
        return 0
    try:
        raw = json.loads(Path(args.json).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("record JSON must be an object")
        payload = RECORDERS[args.kind](cast(dict[str, Any], raw))
    except (OSError, ValueError) as exc:
        return _error("record", exc)
    _print(payload)
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="prodeng")
    root.add_argument("--version", action="version", version=f"prodeng {__version__}")
    sub = root.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor")
    doctor.set_defaults(func=_cmd_doctor)

    validate = sub.add_parser("validate")
    validate.add_argument("contract")
    validate.set_defaults(func=_cmd_validate)

    gates = sub.add_parser("gates")
    gates.add_argument("contract")
    gates.add_argument("--json", action="store_true")
    gates.set_defaults(func=_cmd_gates)

    export = sub.add_parser("export")
    export.add_argument("contract")
    export.add_argument("--out")
    export.set_defaults(func=_cmd_export)

    author = sub.add_parser("author")
    author.add_argument("contract")
    author.add_argument("--out")
    author.add_argument("--render", action="store_true")
    author.set_defaults(func=_cmd_author)

    render = sub.add_parser("render")
    render.add_argument("contract")
    render.add_argument("--out")
    render.set_defaults(func=_cmd_render)

    import_parser = sub.add_parser("import")
    import_parser.add_argument("contract")
    import_parser.add_argument("--from", dest="kind", required=True, choices=tuple(IMPORT_SYSTEMS))
    import_parser.add_argument("file")
    import_parser.set_defaults(func=_cmd_import)

    requests_parser = sub.add_parser("requests")
    requests_parser.add_argument("contract")
    requests_parser.add_argument("--out")
    requests_parser.set_defaults(func=_cmd_requests)

    liaison = sub.add_parser("liaison")
    liaison.add_argument("directory")
    liaison.set_defaults(func=_cmd_liaison)

    ux = sub.add_parser("ux")
    ux_sub = ux.add_subparsers(dest="ux_command", required=True)
    ux_inbox_parser = ux_sub.add_parser("inbox")
    ux_inbox_parser.set_defaults(func=_cmd_ux_inbox)
    ux_respond_parser = ux_sub.add_parser("respond")
    ux_respond_parser.add_argument("--json", required=True)
    ux_respond_parser.set_defaults(func=_cmd_ux_respond)

    sample = sub.add_parser("sample")
    sample.add_argument("--lot", required=True, type=int)
    sample.add_argument("--aql", required=True, type=float)
    sample.add_argument("--level", default="II")
    sample.set_defaults(func=_cmd_sample)

    record = sub.add_parser("record")
    record_kinds = record.add_subparsers(dest="kind", required=True)
    for kind in ("decision", "impression", "vision-review"):
        writer = record_kinds.add_parser(kind)
        writer.add_argument("--json", required=True)
    record_kinds.add_parser("status")
    record.set_defaults(func=_cmd_record)

    mcp = sub.add_parser("mcp_server")
    mcp.set_defaults(func=_cmd_mcp)
    return root


def _run_mcp() -> int:
    from .mcp_server import main as mcp_main

    mcp_main()
    return 0


def _cmd_mcp(_args: argparse.Namespace) -> int:
    return _run_mcp()


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    return arguments.func(arguments)


if __name__ == "__main__":
    sys.exit(main())
