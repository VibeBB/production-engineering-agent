#!/usr/bin/env python3
"""Drive the smart-kettle example through authoring and request derivation.

Run inside the digest-pinned prodeng-tools image for CI smoke checks or
locally from a development environment. Exits non-zero if either CLI stage
fails.

Usage:
    e2e_authoring.py --contract examples/smart-kettle/smart-kettle.prodeng.json \
        --out out/smart-kettle [--requests-out examples/smart-kettle]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--requests-out", type=Path)
    args = parser.parse_args(argv)

    contract = args.contract if args.contract.is_absolute() else ROOT / args.contract
    output = args.out if args.out.is_absolute() else ROOT / args.out
    requests_output = (
        args.requests_out
        if args.requests_out is None or args.requests_out.is_absolute()
        else ROOT / args.requests_out
    )
    author = subprocess.run(
        [
            sys.executable,
            "-m",
            "prodeng",
            "author",
            str(contract),
            "--out",
            str(output),
        ],
        cwd=ROOT,
        check=False,
    )
    if author.returncode:
        return author.returncode
    request_command = [sys.executable, "-m", "prodeng", "requests", str(contract)]
    if requests_output is not None:
        request_command.extend(["--out", str(requests_output)])
    requests = subprocess.run(request_command, cwd=ROOT, check=False)
    return requests.returncode


if __name__ == "__main__":
    sys.exit(main())
