"""Sibling artifact import adapters with SHA-256 provenance."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .contract import ImportedData, ImportRef, ProdengContract

ImportKind = Literal[
    "circuit-brief",
    "circuit-connectivity",
    "mech-envelope",
    "wire-contract",
    "ux-contract",
    "fpga-production",
]
ImportSystem = Literal["circuit", "mech", "wire", "ux", "fpga"]

IMPORT_SYSTEMS: dict[ImportKind, ImportSystem] = {
    "circuit-brief": "circuit",
    "circuit-connectivity": "circuit",
    "mech-envelope": "mech",
    "wire-contract": "wire",
    "ux-contract": "ux",
    "fpga-production": "fpga",
}

_SHA256 = r"^[0-9a-f]{64}$"


class FpgaProductionSource(BaseModel):
    """Strict mirror of fpga-agent's ``<name>.fpga-production.json``.

    ``bitstream`` and the last ``argv`` element are relative to the directory
    holding the artifact.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    system: Literal["fpga"]
    artifact_kind: Literal["fpga_production"]
    design: str = Field(min_length=1)
    contract_sha256: str = Field(pattern=_SHA256)
    gate_report_sha256: str = Field(pattern=_SHA256)
    device_ref: str = Field(min_length=1)
    device_profile: str = Field(min_length=1)
    part: str = Field(min_length=1)
    package: str = Field(min_length=1)
    bitstream: str = Field(min_length=1)
    bitstream_sha256: str = Field(pattern=_SHA256)
    bitstream_bytes: int = Field(gt=0)
    target: Literal["sram", "flash"]
    tool: Literal["openFPGALoader"]
    board: str | None
    cable: str | None
    argv: list[str] = Field(min_length=2)

    @model_validator(mode="after")
    def _consistent(self) -> FpgaProductionSource:
        if Path(self.bitstream).is_absolute():
            raise ValueError("bitstream must be relative to the artifact")
        if self.board is None and self.cable is None:
            raise ValueError("artifact names neither a board nor a cable")
        if self.argv[0] != self.tool or self.argv[-1] != self.bitstream:
            raise ValueError("argv must run the tool on the bitstream")
        if ("-f" in self.argv) != (self.target == "flash"):
            raise ValueError("argv and target disagree on flash programming")
        return self


def _objects(payload: dict[str, object], field: str) -> list[dict[str, object]]:
    return _object_list(payload.get(field, []), field)


def _object_list(value: object, field: str) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise ValueError(f"import field {field!r} must be a list")
    objects: list[dict[str, object]] = []
    for index, item in enumerate(cast(list[object], value)):
        if not isinstance(item, dict):
            raise ValueError(f"import field {field!r}[{index}] must be an object")
        objects.append(cast(dict[str, object], item))
    return objects


def _strings(objects: list[dict[str, object]], field: str, *, optional: bool = False) -> list[str]:
    found: list[str] = []
    for item in objects:
        value = item.get(field)
        if value is None and optional:
            continue
        if not isinstance(value, str) or not value:
            raise ValueError(f"import object requires non-empty {field!r}")
        found.append(value)
    return sorted(set(found))


def extract_import(kind: str, payload: dict[str, object]) -> ImportedData:
    if kind == "circuit-brief":
        parts = _objects(payload, "parts")
        connectors = [part for part in parts if part.get("connector") is True]
        return ImportedData(
            nets=_strings(_objects(payload, "nets"), "name"),
            parts=_strings(parts, "reference"),
            connectors=_strings(connectors, "reference"),
        )
    if kind == "circuit-connectivity":
        return ImportedData(
            nets=_strings(_objects(payload, "nets"), "ref"),
            connectors=_strings(_objects(payload, "connectors"), "ref"),
        )
    if kind == "mech-envelope":
        return ImportedData(anchors=_strings(_objects(payload, "anchors"), "name"))
    if kind == "wire-contract":
        return ImportedData(
            parts=_strings(_objects(payload, "wires"), "id"),
            connectors=_strings(_objects(payload, "connectors"), "id"),
        )
    if kind == "ux-contract":
        product = payload.get("product")
        if not isinstance(product, dict):
            raise ValueError("UX contract requires a product object")
        product_payload = cast(dict[str, object], product)
        surfaces = product_payload.get("surfaces", [])
        return ImportedData(surfaces=_strings(_object_list(surfaces, "product.surfaces"), "id"))
    if kind == "fpga-production":
        try:
            artifact = FpgaProductionSource.model_validate(payload)
        except ValidationError as exc:
            raise ValueError(f"malformed fpga-production artifact: {exc}") from exc
        return ImportedData(parts=[artifact.device_ref])
    raise ValueError(f"unsupported import kind {kind!r}; expected one of {tuple(IMPORT_SYSTEMS)}")


def import_source(
    contract: ProdengContract,
    kind: ImportKind,
    path: Path | str,
    contract_dir: Path | str = ".",
) -> ProdengContract:
    source = Path(path).resolve()
    try:
        raw = source.read_bytes()
        payload_value = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not load import source {source}: {exc}") from exc
    if not isinstance(payload_value, dict):
        raise ValueError(f"import source {source} is not a JSON object")
    payload = cast(dict[str, object], payload_value)
    declared_system = payload.get("system")
    expected_system = IMPORT_SYSTEMS.get(kind)
    if expected_system is None:
        raise ValueError(
            f"unsupported import kind {kind!r}; expected one of {tuple(IMPORT_SYSTEMS)}"
        )
    if kind == "ux-contract":
        if declared_system not in (None, "ux-creator", "ux"):
            raise ValueError(f"UX import declares unexpected system {declared_system!r}")
    elif kind == "circuit-connectivity" and declared_system != "circuit":
        raise ValueError(f"circuit connectivity import declares system {declared_system!r}")
    elif declared_system not in (None, expected_system):
        raise ValueError(f"{kind} import declares unexpected system {declared_system!r}")
    extracted = extract_import(kind, payload)
    relative_path = os.path.relpath(source, Path(contract_dir).resolve())
    reference = ImportRef(
        system=expected_system,
        kind=kind,
        path=relative_path,
        sha256=hashlib.sha256(raw).hexdigest(),
        extracted=extracted,
    )
    retained = [
        item
        for item in contract.imports
        if not (item.system == reference.system and item.path == reference.path)
    ]
    data = contract.model_dump(mode="json")
    data["imports"] = [item.model_dump(mode="json") for item in [*retained, reference]]
    return ProdengContract.model_validate(data)


def write_imported_contract(contract: ProdengContract, path: Path | str) -> Path:
    contract_path = Path(path)
    contract_path.write_text(
        json.dumps(contract.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return contract_path
