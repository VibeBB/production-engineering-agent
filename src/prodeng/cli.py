"""Command-line interface for the deterministic prodeng core."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .contract import ProdengContract, contract_json, load_contract
from .doctor import run_doctor
from .gates import run_gates
from .imports import IMPORT_SYSTEMS, import_source
from .projections import write_projections
from .report import write_report
from .requests import write_requests
from .responses import liaison_status
from .sampling import LEVELS, sampling_plan


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
        request_paths = write_requests(contract, report, contract_path.parent)
        paths.update(write_report(contract, report, out_dir, contract_path.parent))
    except (OSError, ValueError) as exc:
        return _error("author", exc)
    _print(
        {
            **report.to_dict(contract),
            "stage": "author",
            "written": {key: str(value) for key, value in paths.items()},
            "requests": [str(path) for path in request_paths],
        }
    )
    return 0 if report.verdict == "pass" else 1


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
        paths = write_requests(contract, report, out_dir)
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


def _cmd_sample(args: argparse.Namespace) -> int:
    try:
        if args.level not in LEVELS:
            raise ValueError(f"level must be one of {LEVELS}")
        plan = sampling_plan(args.lot, args.aql, args.level)
    except ValueError as exc:
        return _error("sample", exc)
    _print({"verdict": "pass", **plan.__dict__})
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
    author.set_defaults(func=_cmd_author)

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

    sample = sub.add_parser("sample")
    sample.add_argument("--lot", required=True, type=int)
    sample.add_argument("--aql", required=True, type=float)
    sample.add_argument("--level", default="II")
    sample.set_defaults(func=_cmd_sample)

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
