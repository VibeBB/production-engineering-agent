"""Deterministic PNG views of production-engineering projections."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .contract import Operation, ProdengContract
from .projections import line_balance_efficiency, write_projections

CANVAS_WIDTH = 1600
MAX_HEIGHT = 6000
MARGIN = 40
PAGE_HEADER_HEIGHT = 130
TABLE_HEADER_HEIGHT = 62
LINE_HEIGHT = 26
FONT_ENV = "PRODENG_RENDER_FONT"
FONT_FALLBACKS = (
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
)

type Color = tuple[int, int, int]
type RowShade = Callable[[tuple[str, ...]], Color | None]

WHITE: Color = (255, 255, 255)
INK: Color = (26, 38, 49)
GRID: Color = (186, 197, 206)
HEADER: Color = (25, 51, 73)
TABLE_HEADER: Color = (225, 234, 240)
PALE_RED: Color = (255, 231, 228)
RED: Color = (193, 42, 35)
AMBER: Color = (226, 160, 38)
GREY: Color = (156, 166, 175)
BLUE: Color = (41, 112, 157)
SAFETY: Color = (255, 244, 202)


@dataclass(frozen=True)
class _TableRow:
    values: tuple[str, ...]
    wrapped: tuple[tuple[str, ...], ...]
    shade: Color | None

    @property
    def height(self) -> int:
        return max(len(lines) for lines in self.wrapped) * LINE_HEIGHT + 20


@lru_cache(maxsize=16)
def _font_file(override: str | None) -> Path | None:
    candidates = ([Path(override).expanduser()] if override else []) + list(FONT_FALLBACKS)
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            ImageFont.truetype(str(candidate), size=18)
        except OSError:
            continue
        return candidate
    return None


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_file = _font_file(os.environ.get(FONT_ENV))
    if font_file is not None:
        return ImageFont.truetype(str(font_file), size=size)
    return ImageFont.load_default(size=size)


def _text_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    width: int,
) -> list[str]:
    output: list[str] = []
    paragraphs = text.replace("\r", "").split("\n")
    for paragraph in paragraphs:
        words = paragraph.split()
        if not words:
            output.append("")
            continue
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if draw.textlength(candidate, font=font) <= width:
                current = candidate
                continue
            if current:
                output.append(current)
                current = ""
            part = ""
            for character in word:
                candidate_part = part + character
                if part and draw.textlength(candidate_part, font=font) > width:
                    output.append(part)
                    part = character
                else:
                    part = candidate_part
            current = part
        if current:
            output.append(current)
    return output or [""]


def _widths(weights: Sequence[int]) -> list[int]:
    total = CANVAS_WIDTH - 2 * MARGIN
    denominator = sum(weights)
    result = [total * weight // denominator for weight in weights]
    result[-1] += total - sum(result)
    return result


def _nice_axis_ticks(max_value: float) -> tuple[float, list[float]]:
    target = max_value * 1.05
    exponent = math.floor(math.log10(target))
    candidates: list[tuple[float, float]] = []
    for power in range(exponent - 4, exponent + 2):
        magnitude = 10**power
        for multiplier in (1, 2, 5):
            step = multiplier * magnitude
            axis_max = math.ceil(target / step) * step
            count = round(axis_max / step) + 1
            if 4 <= count <= 8:
                candidates.append((axis_max, step))
    if not candidates:
        raise ValueError("could not find readable line-balance axis ticks")
    axis_max, step = min(candidates)
    tick_count = round(axis_max / step)
    return step, [index * step for index in range(tick_count + 1)]


def _axis_tick_label(value: float, step: float) -> str:
    if math.isclose(step, round(step), rel_tol=0.0, abs_tol=1e-10):
        return str(round(value))
    return f"{value:g}"


def _takt_utilization_label(cycle_time_s: float, takt_s: float) -> str:
    utilization = round(cycle_time_s / takt_s * 100)
    return f"{cycle_time_s:g} s ({utilization}%)"


def _prepare_rows(
    rows: Sequence[tuple[str, ...]],
    widths: Sequence[int],
    shade: RowShade | None,
) -> list[_TableRow]:
    font = _font(18)
    probe = Image.new("RGB", (1, 1), WHITE)
    draw = ImageDraw.Draw(probe)
    max_segment_lines = 170
    prepared: list[_TableRow] = []
    for values in rows:
        wrapped = tuple(
            tuple(_text_lines(draw, value, font, width - 20))
            for value, width in zip(values, widths, strict=True)
        )
        shade_color = shade(values) if shade is not None else None
        line_count = max(len(lines) for lines in wrapped)
        if line_count <= max_segment_lines:
            prepared.append(_TableRow(values, wrapped, shade_color))
            continue
        for start in range(0, line_count, max_segment_lines):
            end = start + max_segment_lines
            segment = tuple(tuple(lines[start:end]) or ("",) for lines in wrapped)
            prepared.append(_TableRow(values, segment, shade_color))
    return prepared


def _table_page_groups(rows: Sequence[_TableRow]) -> list[list[_TableRow]]:
    pages: list[list[_TableRow]] = []
    page: list[_TableRow] = []
    used = PAGE_HEADER_HEIGHT + TABLE_HEADER_HEIGHT + MARGIN
    for row in rows:
        if page and used + row.height > MAX_HEIGHT - MARGIN:
            pages.append(page)
            page = []
            used = PAGE_HEADER_HEIGHT + TABLE_HEADER_HEIGHT + MARGIN
        page.append(row)
        used += row.height
    if page or not pages:
        pages.append(page)
    return pages


def _save_png(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=False, compress_level=9)


def _draw_page_header(
    draw: ImageDraw.ImageDraw,
    product: ProdengContract,
    title: str,
    page_number: int,
    total_pages: int,
) -> None:
    draw.rectangle((0, 0, CANVAS_WIDTH, PAGE_HEADER_HEIGHT), fill=HEADER)
    small = _font(20)
    large = _font(30)
    draw.text(
        (MARGIN, 14),
        f"{product.product.name} | Revision {product.product.revision}",
        font=small,
        fill=WHITE,
    )
    draw.text(
        (MARGIN, 48),
        title,
        font=large,
        fill=WHITE,
    )
    page_text = f"Page {page_number} of {total_pages}"
    page_width = int(draw.textlength(page_text, font=small))
    draw.text((CANVAS_WIDTH - MARGIN - page_width, 18), page_text, font=small, fill=WHITE)


def _render_table(
    product: ProdengContract,
    render_dir: Path,
    base_name: str,
    title: str,
    headers: tuple[str, ...],
    rows: Sequence[tuple[str, ...]],
    weights: tuple[int, ...],
    *,
    shade: RowShade | None = None,
    swatch_column: int | None = None,
) -> list[Path]:
    column_widths = _widths(weights)
    prepared = _prepare_rows(rows, column_widths, shade)
    page_rows = _table_page_groups(prepared)
    paths: list[Path] = []
    body_font = _font(18)
    header_font = _font(18)
    swatches = {"critical": RED, "major": AMBER, "minor": GREY}
    for page_number, group in enumerate(page_rows, start=1):
        height = (
            PAGE_HEADER_HEIGHT + TABLE_HEADER_HEIGHT + MARGIN + sum(row.height for row in group)
        )
        height = min(MAX_HEIGHT, max(height, PAGE_HEADER_HEIGHT + TABLE_HEADER_HEIGHT + MARGIN))
        image = Image.new("RGB", (CANVAS_WIDTH, height), WHITE)
        draw = ImageDraw.Draw(image)
        _draw_page_header(draw, product, title, page_number, len(page_rows))
        y = PAGE_HEADER_HEIGHT
        x = MARGIN
        for header, width in zip(headers, column_widths, strict=True):
            draw.rectangle((x, y, x + width, y + TABLE_HEADER_HEIGHT), fill=TABLE_HEADER)
            draw.rectangle((x, y, x + width, y + TABLE_HEADER_HEIGHT), outline=GRID, width=1)
            lines = _text_lines(draw, header, header_font, width - 20)
            draw.multiline_text(
                (x + 10, y + 8),
                "\n".join(lines),
                font=header_font,
                fill=INK,
                spacing=3,
            )
            x += width
        y += TABLE_HEADER_HEIGHT
        for row in group:
            x = MARGIN
            row_height = row.height
            for index, (value_lines, width) in enumerate(
                zip(row.wrapped, column_widths, strict=True)
            ):
                fill = row.shade or WHITE
                draw.rectangle((x, y, x + width, y + row_height), fill=fill)
                draw.rectangle((x, y, x + width, y + row_height), outline=GRID, width=1)
                if swatch_column == index:
                    swatch = swatches.get(row.values[index].lower())
                    if swatch is not None:
                        draw.rectangle((x + 9, y + 11, x + 25, y + row_height - 11), fill=swatch)
                draw.multiline_text(
                    (x + (32 if swatch_column == index else 10), y + 9),
                    "\n".join(value_lines),
                    font=body_font,
                    fill=INK,
                    spacing=3,
                )
                x += width
            y += row_height
        path_name = f"{base_name}.png" if len(page_rows) == 1 else f"{base_name}-p{page_number}.png"
        path = render_dir / path_name
        _save_png(image, path)
        paths.append(path)
    return paths


def _control_plan_rows(contract: ProdengContract) -> list[tuple[str, ...]]:
    characteristics = {item.id: item for item in contract.characteristics}
    operations = {item.id: item for item in contract.operations}
    rows: list[tuple[str, ...]] = []
    for inspection in sorted(contract.inspections, key=lambda item: item.id):
        characteristic = characteristics[inspection.characteristic]
        operation = operations[inspection.operation]
        sampling = inspection.sampling
        if sampling.mode == "full":
            sample_text = "Full inspection"
        elif sampling.aql is None:
            sample_text = f"AQL missing, level {sampling.level}"
        else:
            sample_text = f"AQL {sampling.aql:g}, level {sampling.level}"
        rows.append(
            (
                f"{characteristic.id} - {characteristic.description}",
                characteristic.classification,
                f"{operation.id} - {operation.name}",
                inspection.method,
                sample_text,
                inspection.equipment,
                inspection.reaction_plan,
            )
        )
    return rows


def _pfmea_rows(contract: ProdengContract) -> list[tuple[str, ...]]:
    return [
        (
            item.id,
            item.operation,
            item.mode,
            item.effect,
            item.cause,
            str(item.severity),
            str(item.occurrence),
            str(item.detection),
            str(item.severity * item.occurrence * item.detection),
            "\n".join(sorted(item.controls)),
        )
        for item in sorted(contract.failure_modes, key=lambda item: item.id)
    ]


def _pfmea_shade(values: tuple[str, ...]) -> Color | None:
    return PALE_RED if int(values[5]) >= 9 else None


def _operation_rows(operation: Operation) -> list[tuple[str, ...]]:
    rows: list[tuple[str, ...]] = []
    for index, element in enumerate(operation.work_elements, start=1):
        key_points = [
            f"SAFETY: {point}" if _is_safety_point(point) else point for point in element.key_points
        ]
        rows.append(
            (
                f"{index}. {element.step}",
                "\n".join(key_points),
                "\n".join(element.reasons),
            )
        )
    rows.extend(("Safety hazard", f"SAFETY: {hazard}", "") for hazard in operation.safety_hazards)
    rows.extend(
        ("Safety key point", f"SAFETY: {precaution}", "")
        for precaution in operation.safety_precautions
    )
    return rows or [("No work elements declared", "", "")]


def _is_safety_point(value: str) -> bool:
    return bool(
        re.search(
            r"\b(safety|hazard|shock|hot|heat|voltage|power|lockout|guard|esd|protective|ppe)\b",
            value,
            re.IGNORECASE,
        )
    )


def _display_list(items: Sequence[str]) -> str:
    return "\n".join(items) if items else "none"


def _ftm_rows(contract: ProdengContract) -> list[tuple[str, ...]]:
    ftm = contract.factory_test_mode
    if ftm is None:
        return [("Factory test mode", "None declared", "No FTM contract.")]
    rows = [
        ("Entry", "Method", ftm.entry.method),
        ("Entry", "Detail", ftm.entry.detail),
        ("Entry", "Conditions", "\n".join(ftm.entry.conditions)),
        ("Field lockout", ftm.field_lockout.method, ftm.field_lockout.detail),
        (
            "Interface",
            ftm.interface.transport,
            f"Settings: {ftm.interface.settings}\nNets:\n"
            + _display_list(sorted(ftm.interface.nets)),
        ),
    ]
    command_rows = [
        (
            "Command",
            f"{command.id} - {command.name}",
            f"{command.request} -> {command.response_pattern}\n"
            f"Timeout: {command.timeout_ms} ms\n"
            f"Measures:\n{_display_list(sorted(command.measures_nets))}\n"
            f"Covers:\n{_display_list(sorted(command.covers))}",
        )
        for command in sorted(ftm.commands, key=lambda item: item.id)
    ]
    rows.extend(command_rows or [("Command", "None declared", "")])
    provisioning_rows = [
        (
            "Provisioning",
            item.item,
            f"Source: {item.source}; write once: {str(item.write_once).lower()}",
        )
        for item in ftm.provisioning
    ]
    rows.extend(provisioning_rows or [("Provisioning", "None declared", "")])
    rows.extend(
        [
            ("Exit", "Procedure", ftm.exit),
            ("Duration", "Maximum", f"{ftm.max_duration_s:g} s"),
            (
                "Duration",
                "Command timeout budget",
                f"{sum(command.timeout_ms for command in ftm.commands) / 1000:g} s",
            ),
        ]
    )
    return rows


def _line_balance_summary(
    contract: ProdengContract,
    efficiency: float | None,
) -> tuple[str, str]:
    efficiency_text = (
        "Balance efficiency unknown"
        if efficiency is None
        else f"Balance efficiency {efficiency * 100:.1f}%"
    )
    efficiency_text += " (sum of cycle times / (operations x takt))"
    bottleneck = max(
        (operation for operation in contract.operations if operation.cycle_time_s is not None),
        key=lambda operation: operation.cycle_time_s or 0.0,
        default=None,
    )
    if bottleneck is None or bottleneck.cycle_time_s is None:
        return efficiency_text, "Bottleneck unknown"
    takt = contract.volume.takt_s
    utilization = round(bottleneck.cycle_time_s / takt * 100)
    bottleneck_text = (
        f"Bottleneck {bottleneck.id} - {bottleneck.name}: "
        f"{bottleneck.cycle_time_s:g} s ({utilization}% of takt {takt:g} s)"
    )
    return efficiency_text, bottleneck_text


def _render_line_balance(
    contract: ProdengContract,
    render_dir: Path,
    efficiency: float | None,
) -> list[Path]:
    operations = sorted(contract.operations, key=lambda item: item.id)
    takt = contract.volume.takt_s
    known = [
        operation.cycle_time_s for operation in operations if operation.cycle_time_s is not None
    ]
    step, ticks = _nice_axis_ticks(max([takt, *known]))
    axis_max = ticks[-1]
    plot_left = 360
    plot_right = CANVAS_WIDTH - MARGIN
    plot_width = plot_right - plot_left
    row_height = 64
    per_page = max(1, (MAX_HEIGHT - 340) // row_height)
    operation_pages = [
        operations[start : start + per_page] for start in range(0, len(operations), per_page)
    ] or [[]]
    paths: list[Path] = []
    for page_number, page_operations in enumerate(operation_pages, start=1):
        plot_top = PAGE_HEADER_HEIGHT + 105
        axis_y = plot_top + len(page_operations) * row_height + 20
        height = min(MAX_HEIGHT, axis_y + 105)
        image = Image.new("RGB", (CANVAS_WIDTH, height), WHITE)
        draw = ImageDraw.Draw(image)
        _draw_page_header(
            draw, contract, "Line balance by operation", page_number, len(operation_pages)
        )
        small = _font(18)
        label_font = _font(18)
        efficiency_text, bottleneck_text = _line_balance_summary(contract, efficiency)
        draw.text(
            (MARGIN, PAGE_HEADER_HEIGHT + 12),
            efficiency_text,
            font=small,
            fill=INK,
        )
        draw.text(
            (MARGIN, PAGE_HEADER_HEIGHT + 39),
            bottleneck_text,
            font=small,
            fill=INK,
        )
        for value in ticks:
            x = plot_left + round(value / axis_max * plot_width)
            draw.line((x, plot_top - 14, x, axis_y), fill=(226, 232, 237), width=1)
        takt_x = plot_left + round(takt / axis_max * plot_width)
        draw.line((takt_x, plot_top - 14, takt_x, axis_y), fill=RED, width=3)
        takt_label = f"TAKT {takt:g} s"
        draw.text((takt_x + 5, plot_top - 39), takt_label, font=small, fill=RED)
        for index, operation in enumerate(page_operations):
            y = plot_top + index * row_height
            label = f"{operation.id} - {operation.name}"
            lines = _text_lines(draw, label, label_font, plot_left - MARGIN - 20)
            draw.multiline_text(
                (MARGIN, y + 10),
                "\n".join(lines[:2]),
                font=label_font,
                fill=INK,
                spacing=2,
            )
            if operation.cycle_time_s is None:
                draw.text((plot_left, y + 15), "Cycle time unknown", font=small, fill=GREY)
            else:
                bar_end = plot_left + round(operation.cycle_time_s / axis_max * plot_width)
                bar_color = RED if operation.cycle_time_s > takt else BLUE
                draw.rounded_rectangle(
                    (plot_left, y + 13, max(plot_left + 2, bar_end), y + 43),
                    radius=4,
                    fill=bar_color,
                )
                bar_label = _takt_utilization_label(operation.cycle_time_s, takt)
                label_width = draw.textlength(bar_label, font=small)
                draw.text(
                    (min(bar_end + 8, plot_right - label_width - 8), y + 13),
                    bar_label,
                    font=small,
                    fill=INK,
                )
        draw.line((plot_left, axis_y, plot_right, axis_y), fill=INK, width=2)
        for value in ticks:
            x = plot_left + round(value / axis_max * plot_width)
            draw.line((x, axis_y - 5, x, axis_y + 5), fill=INK, width=1)
            tick_label = _axis_tick_label(value, step)
            tick_width = draw.textlength(tick_label, font=small)
            label_x = min(max(plot_left, x - round(tick_width / 2)), plot_right - tick_width)
            draw.text((label_x, axis_y + 12), tick_label, font=small, fill=INK)
        draw.text((plot_right - 70, axis_y + 40), "seconds", font=small, fill=INK)
        path_name = (
            "line-balance.png" if len(operation_pages) == 1 else f"line-balance-p{page_number}.png"
        )
        path = render_dir / path_name
        _save_png(image, path)
        paths.append(path)
    return paths


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_hashes(contract: ProdengContract) -> dict[str, tuple[str, str]]:
    with tempfile.TemporaryDirectory(prefix="prodeng-render-source-") as temp:
        generated = write_projections(contract, contract.product.name, Path(temp))
        source_names = {
            "control-plan": ("control-plan.csv", generated["control_plan"]),
            "pfmea": ("pfmea.csv", generated["pfmea"]),
            "line-balance": ("line-balance.csv", generated["line_balance"]),
            "work-instruction": ("work-instructions.md", generated["work_instructions"]),
            "factory-test-spec": ("factory-test-spec.json", generated["factory_test_json"]),
        }
        return {
            key: (filename, _sha256_file(path)) for key, (filename, path) in source_names.items()
        }


def render_sheets(contract: ProdengContract, out_dir: Path) -> dict[str, Path]:
    render_dir = out_dir / "renders"
    render_dir.mkdir(parents=True, exist_ok=True)
    source_hashes = _source_hashes(contract)
    rendered: dict[str, Path] = {}
    index_rows: list[dict[str, str]] = []

    render_jobs: list[tuple[str, str, list[Path]]] = []
    render_jobs.append(
        (
            "control-plan",
            "control-plan",
            _render_table(
                contract,
                render_dir,
                "control-plan",
                "Control plan",
                (
                    "Characteristic",
                    "Class",
                    "Operation",
                    "Method",
                    "Sampling",
                    "Equipment",
                    "Reaction plan",
                ),
                _control_plan_rows(contract),
                (5, 2, 5, 3, 3, 5, 7),
                swatch_column=1,
            ),
        )
    )
    render_jobs.append(
        (
            "pfmea",
            "pfmea",
            _render_table(
                contract,
                render_dir,
                "pfmea",
                "Process failure mode and effects analysis",
                (
                    "ID",
                    "Operation",
                    "Failure mode",
                    "Effect",
                    "Cause",
                    "S",
                    "O",
                    "D",
                    "RPN",
                    "Controls",
                ),
                _pfmea_rows(contract),
                (2, 2, 4, 4, 4, 1, 1, 1, 2, 3),
                shade=_pfmea_shade,
            ),
        )
    )
    render_jobs.append(
        (
            "line-balance",
            "line-balance",
            _render_line_balance(contract, render_dir, line_balance_efficiency(contract)),
        )
    )
    for operation in sorted(contract.operations, key=lambda item: item.id):
        key = f"work-instruction-{operation.id}"
        render_jobs.append(
            (
                key,
                "work-instruction",
                _render_table(
                    contract,
                    render_dir,
                    key,
                    f"Work instruction - {operation.id} {operation.name}",
                    ("Major step", "Key points", "Reasons"),
                    _operation_rows(operation),
                    (5, 6, 5),
                    shade=lambda values: (
                        SAFETY if values[0].startswith("Safety key point") else None
                    ),
                ),
            )
        )
    render_jobs.append(
        (
            "factory-test-spec",
            "factory-test-spec",
            _render_table(
                contract,
                render_dir,
                "factory-test-spec",
                "Factory test specification",
                ("Section", "Field", "Details"),
                _ftm_rows(contract),
                (3, 4, 12),
            ),
        )
    )
    for _, source_key, paths in render_jobs:
        source_name, source_hash = source_hashes[source_key]
        for path in paths:
            rendered[path.stem] = path
            index_rows.append(
                {
                    "name": path.stem,
                    "path": path.relative_to(out_dir).as_posix(),
                    "sha256": _sha256_file(path),
                    "source": source_name,
                    "source_sha256": source_hash,
                }
            )
    font_file = _font_file(os.environ.get(FONT_ENV))
    index = {
        "schema_version": 1,
        "product": contract.product.name,
        "font": font_file.name if font_file is not None else "pillow-default",
        "renders": sorted(index_rows, key=lambda item: (item["name"], item["path"])),
    }
    (render_dir / "index.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return rendered
