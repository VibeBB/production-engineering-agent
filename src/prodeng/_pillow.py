"""Check optional Pillow support without importing it at module load time."""

from __future__ import annotations

import importlib

_RENDER_UNAVAILABLE_REASON = (
    "Pillow is not installed in this prodeng-tools image; renders need an image "
    "published after this change (update docker/image-digests.json)."
)


def render_unavailable_reason() -> str | None:
    try:
        for module in ("PIL", "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont"):
            importlib.import_module(module)
    except ImportError:
        return _RENDER_UNAVAILABLE_REASON
    return None
