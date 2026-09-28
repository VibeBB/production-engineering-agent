"""Verify Markdown links and the ADR index."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
SKIP_PARTS = {".git", ".venv", "node_modules", "out"}
EXPECTED_ADRS = (
    "0001-deterministic-core-and-gates.md",
    "0002-iso-2859-sampling-tables.md",
    "0003-sibling-cooperation-via-contracts.md",
    "0004-factory-test-mode-contract.md",
    "0005-work-instructions-twi.md",
)


def check_links() -> list[str]:
    errors: list[str] = []
    for markdown in ROOT.rglob("*.md"):
        if any(part in SKIP_PARTS for part in markdown.parts):
            continue
        for target in LINK_PATTERN.findall(markdown.read_text(encoding="utf-8")):
            target = target.strip().strip("<>")
            if target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            path: Path = (markdown.parent / unquote(target.split("#", 1)[0])).resolve()
            if not path.exists():
                errors.append(f"{markdown.relative_to(ROOT)}: missing {target}")
    return errors


def check_adr_index() -> list[str]:
    index = (ROOT / "docs/README.md").read_text(encoding="utf-8")
    errors: list[str] = []
    for name in EXPECTED_ADRS:
        adr = ROOT / "docs/adr" / name
        relative = adr.relative_to(ROOT / "docs").as_posix()
        if not adr.is_file():
            errors.append(f"missing required ADR {relative}")
            continue
        if relative not in index:
            errors.append(f"docs/README.md: missing ADR {relative}")
    return errors


def main() -> int:
    errors = check_links() + check_adr_index()
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("documentation verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
