"""Structured and human-readable production-engineering reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contract import ProdengContract
from .gates import GateReport
from .responses import liaison_status


def build_report(
    contract: ProdengContract,
    gate_report: GateReport,
    out_dir: Path,
    request_dir: Path | None = None,
) -> dict[str, Any]:
    liaison = liaison_status(request_dir or out_dir)
    by_state = {
        state: sum(entry.state == state for entry in liaison.entries)
        for state in ("open", "answered", "mismatched")
    }
    by_gate_status = {
        status: sum(check.status == status for check in gate_report.checks)
        for status in ("pass", "fail", "unknown")
    }
    return {
        "schema_version": 1,
        "system": "prodeng",
        "product": {
            "name": contract.product.name,
            "revision": contract.product.revision,
        },
        "verdict": gate_report.verdict,
        "gates": gate_report.to_dict(contract),
        "liaison": {
            **by_state,
            "by_response_status": {
                status: sum(entry.response_status == status for entry in liaison.entries)
                for status in ("accepted", "rejected", "deferred", "needs_info")
            },
            "orphans": liaison.orphans,
            "malformed": liaison.malformed,
        },
        "counts": {
            "requirements": len(contract.requirements),
            "characteristics": len(contract.characteristics),
            "operations": len(contract.operations),
            "inspections": len(contract.inspections),
            "failure_modes": len(contract.failure_modes),
            "gate_checks": by_gate_status,
        },
        "takt_s": contract.volume.takt_s,
    }


def render_markdown(report: dict[str, Any]) -> str:
    product = report["product"]
    gates = report["gates"]
    gate_checks = gates["checks"]
    lines = [
        f"# Production engineering report — {product['name']}",
        "",
        f"Revision: {product['revision']}",
        f"Verdict: **{report['verdict']}**",
        f"Takt: {report['takt_s']:.3f} s/unit",
        "",
        "## Gate checks",
        "",
        "| Check | Subject | Status | Measured | Limit | Detail |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for check in gate_checks:
        detail = str(check["detail"]).replace("|", "\\|")
        lines.append(
            f"| {check['id']} | {check['subject']} | {check['status']} | "
            f"{check['measured'] if check['measured'] is not None else ''} | "
            f"{check['limit'] if check['limit'] is not None else ''} | "
            f"{detail} |"
        )
    liaison = report["liaison"]
    lines.extend(
        [
            "",
            "## Liaison",
            "",
            f"Requests: {liaison['open'] + liaison['answered'] + liaison['mismatched']}; "
            f"open: {liaison['open']}; answered: {liaison['answered']}; "
            f"mismatched: {liaison['mismatched']}.",
            f"Orphans: {len(liaison['orphans'])}; malformed files: {len(liaison['malformed'])}.",
        ]
    )
    return "\n".join(lines)


def write_report(
    contract: ProdengContract,
    gate_report: GateReport,
    out_dir: Path,
    request_dir: Path | None = None,
) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    report = build_report(contract, gate_report, out_dir, request_dir)
    json_path = out_dir / "prodeng-report.json"
    markdown_path = out_dir / "prodeng-report.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report) + "\n", encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path}
