"""Report the Python and package versions used by the core."""

from __future__ import annotations

import json
import platform
from importlib.metadata import PackageNotFoundError, version

from . import __version__
from ._pillow import render_unavailable_reason


def _package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "not installed"


def run_doctor() -> dict[str, object]:
    pillow_reason = render_unavailable_reason()
    return {
        "verdict": "pass",
        "python": platform.python_version(),
        "pydantic": _package_version("pydantic"),
        "pillow": f"missing: {pillow_reason}" if pillow_reason else _package_version("pillow"),
        "production-engineering-agent": __version__,
    }


def main() -> int:
    print(json.dumps(run_doctor(), indent=2, sort_keys=True))
    return 0
