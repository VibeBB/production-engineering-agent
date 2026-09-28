#!/usr/bin/env python3
"""Run the lightweight session-start doctor through the locked-image launcher."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    launcher = PLUGIN_ROOT / "scripts" / "prodeng_launcher.py"
    return subprocess.run(
        [sys.executable, str(launcher), "doctor", "--warn"],
        check=False,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
