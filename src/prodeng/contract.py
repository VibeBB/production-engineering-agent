"""Typed contract schema and load-time reference validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .sampling import AQL_VALUES, LEVELS

SYSTEM = "prodeng"


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Product(FrozenModel):
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    revision: str = Field(min_length=1)
    description: str = ""


class Volume(FrozenModel):
    annual_demand_units: int = Field(gt=0)
    working_days_per_year: int = Field(gt=0)
    shifts_per_day: int = Field(gt=0)
    available_minutes_per_shift: float = Field(gt=0)
    lot_size: int = Field(ge=2)

    @property
    def takt_s(self) -> float:
        return (
            self.working_days_per_year
            * self.shifts_per_day
            * self.available_minutes_per_shift
            * 60
            / self.annual_demand_units
        )


class Requirement(FrozenModel):
    id: str = Field(pattern=r"^[RAQ][0-9]+$")
    kind: Literal["assumption", "requirement", "question"]
    text: str = Field(min_length=1)
    status: Literal["open", "resolved"] = "resolved"

    @model_validator(mode="after")
    def prefix_matches_kind(self) -> Requirement:
        expected = {"R": "requirement", "A": "assumption", "Q": "question"}[self.id[0]]
        if self.kind != expected:
            raise ValueError(f"{self.id} requires kind {expected!r}")
        return self


class Characteristic(FrozenModel):
    id: str = Field(pattern=r"^CH-[0-9]{2,4}$")
    description: str = Field(min_length=1)
    classification: Literal["critical", "major", "minor"]
    kind: Literal["variable", "attribute"]
    unit: str | None = None
    nominal: float | None = None
    lsl: float | None = None
    usl: float | None = None
    criterion: str = ""
    sources: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_type_requirements(self) -> Characteristic:
        if self.lsl is not None and self.usl is not None and self.lsl > self.usl:
            raise ValueError(f"{self.id} lsl must be <= usl")
        if self.nominal is not None and self.lsl is not None and self.nominal < self.lsl:
            raise ValueError(f"{self.id} nominal must be >= lsl")
        if self.nominal is not None and self.usl is not None and self.nominal > self.usl:
            raise ValueError(f"{self.id} nominal must be <= usl")
        if self.kind == "variable":
            if not self.unit:
                raise ValueError(f"{self.id} variable characteristic requires unit")
            if self.lsl is None and self.usl is None:
                raise ValueError(f"{self.id} variable characteristic requires lsl or usl")
        elif not self.criterion:
            raise ValueError(f"{self.id} attribute characteristic requires criterion")
        return self


class WorkElement(FrozenModel):
    step: str = Field(min_length=1)
    key_points: list[str] = Field(default_factory=list[str])
    reasons: list[str] = Field(default_factory=list[str])


class Operation(FrozenModel):
    id: str = Field(pattern=r"^OP[0-9]{2,4}$")
    name: str = Field(min_length=1)
    kind: Literal[
        "smt",
        "tht",
        "selective_solder",
        "harness",
        "mechanical_assembly",
        "programming",
        "test",
        "inspection",
        "packing",
        "other",
    ]
    station: str = Field(min_length=1)
    cycle_time_s: float | None = Field(default=None, gt=0)
    operators: int = Field(ge=0)
    tools: list[str] = Field(default_factory=list[str])
    fixtures: list[str] = Field(default_factory=list[str])
    esd_sensitive: bool = False
    safety_hazards: list[str] = Field(default_factory=list[str])
    safety_precautions: list[str] = Field(default_factory=list[str])
    work_elements: list[WorkElement] = Field(default_factory=list[WorkElement])
    programs: list[str] = Field(default_factory=list[str])


class SamplingSpec(FrozenModel):
    mode: Literal["full", "aql"]
    aql: float | None = None
    level: Literal["I", "II", "III", "S-1", "S-2", "S-3", "S-4"] = "II"

    @model_validator(mode="after")
    def validate_sampling(self) -> SamplingSpec:
        if self.mode == "aql":
            if self.aql is None or not any(abs(self.aql - aql) < 1e-9 for aql in AQL_VALUES):
                raise ValueError(f"aql must be one of {AQL_VALUES}")
            if self.level not in LEVELS:
                raise ValueError(f"level must be one of {LEVELS}")
        elif self.aql is not None:
            raise ValueError("full sampling must not specify aql")
        return self


class Inspection(FrozenModel):
    id: str = Field(pattern=r"^IN-[0-9]{2,4}$")
    characteristic: str = Field(pattern=r"^CH-[0-9]{2,4}$")
    operation: str = Field(pattern=r"^OP[0-9]{2,4}$")
    method: Literal[
        "visual",
        "spi",
        "aoi",
        "axi",
        "ict",
        "flying_probe",
        "boundary_scan",
        "fct",
        "hipot",
        "ground_bond",
        "measurement",
        "burn_in",
    ]
    sampling: SamplingSpec
    equipment: str = Field(min_length=1)
    reaction_plan: str = Field(min_length=1)
    ftm_commands: list[str] = Field(default_factory=list[str])


class FailureMode(FrozenModel):
    id: str = Field(pattern=r"^FM-[0-9]{2,4}$")
    operation: str = Field(pattern=r"^OP[0-9]{2,4}$")
    mode: str = Field(min_length=1)
    effect: str = Field(min_length=1)
    cause: str = Field(min_length=1)
    severity: int = Field(ge=1, le=10)
    occurrence: int = Field(ge=1, le=10)
    detection: int = Field(ge=1, le=10)
    controls: list[str] = Field(default_factory=list[str])


class FtmEntry(FrozenModel):
    method: Literal["gpio_strap", "uart_magic", "button_combo", "test_pad", "jtag_swd", "other"]
    detail: str = Field(min_length=1)
    conditions: list[str] = Field(min_length=1)


class FieldLockout(FrozenModel):
    method: Literal["otp_fuse", "nvm_flag", "signed_token", "physical_removal", "none"]
    detail: str = Field(min_length=1)


class FtmInterface(FrozenModel):
    transport: Literal["uart", "usb_cdc", "swd", "jtag", "i2c", "spi", "can", "ble", "other"]
    settings: str = Field(min_length=1)
    nets: list[str] = Field(default_factory=list[str])


class FtmCommand(FrozenModel):
    id: str = Field(pattern=r"^TC-[0-9]{2,4}$")
    name: str = Field(min_length=1)
    request: str = Field(min_length=1)
    response_pattern: str = Field(min_length=1)
    timeout_ms: int = Field(gt=0)
    measures_nets: list[str] = Field(default_factory=list[str])
    covers: list[str] = Field(default_factory=list[str])
    destructive: bool = False


class Provisioning(FrozenModel):
    item: Literal[
        "serial_number",
        "mac_address",
        "calibration",
        "license_key",
        "device_certificate",
        "other",
    ]
    source: str = Field(min_length=1)
    write_once: bool = True


class FactoryTestMode(FrozenModel):
    entry: FtmEntry
    field_lockout: FieldLockout
    interface: FtmInterface
    commands: list[FtmCommand] = Field(default_factory=list[FtmCommand])
    provisioning: list[Provisioning] = Field(default_factory=list[Provisioning])
    exit: str = Field(min_length=1)
    max_duration_s: float = Field(gt=0)


class ImportedData(FrozenModel):
    nets: list[str] = Field(default_factory=list[str])
    parts: list[str] = Field(default_factory=list[str])
    connectors: list[str] = Field(default_factory=list[str])
    anchors: list[str] = Field(default_factory=list[str])
    surfaces: list[str] = Field(default_factory=list[str])


class ImportRef(FrozenModel):
    system: Literal["circuit", "mech", "wire", "ux", "fpga"]
    kind: (
        Literal[
            "circuit-brief",
            "circuit-connectivity",
            "mech-envelope",
            "wire-contract",
            "ux-contract",
            "fpga-production",
        ]
        | None
    ) = None
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    extracted: ImportedData = Field(default_factory=ImportedData)


class ProdengContract(FrozenModel):
    schema_version: Literal[1]
    system: Literal["prodeng"]
    product: Product
    volume: Volume
    requirements: list[Requirement] = Field(default_factory=list[Requirement])
    characteristics: list[Characteristic] = Field(default_factory=list[Characteristic])
    operations: list[Operation] = Field(default_factory=list[Operation])
    inspections: list[Inspection] = Field(default_factory=list[Inspection])
    failure_modes: list[FailureMode] = Field(default_factory=list[FailureMode])
    factory_test_mode: FactoryTestMode | None = None
    imports: list[ImportRef] = Field(default_factory=list[ImportRef])

    @model_validator(mode="after")
    def validate_references(self) -> ProdengContract:
        collections: tuple[tuple[str, list[str]], ...] = (
            ("requirements", [item.id for item in self.requirements]),
            ("characteristics", [item.id for item in self.characteristics]),
            ("operations", [item.id for item in self.operations]),
            ("inspections", [item.id for item in self.inspections]),
            ("failure_modes", [item.id for item in self.failure_modes]),
            (
                "ftm commands",
                [item.id for item in self.factory_test_mode.commands]
                if self.factory_test_mode
                else [],
            ),
        )
        for label, ids in collections:
            if len(ids) != len(set(ids)):
                raise ValueError(f"duplicate id in {label}")
        requirements = {item.id for item in self.requirements}
        characteristics = {item.id for item in self.characteristics}
        operations = {item.id for item in self.operations}
        inspections = {item.id for item in self.inspections}
        commands: set[str] = (
            {item.id for item in self.factory_test_mode.commands}
            if self.factory_test_mode
            else set()
        )
        imports = {item.system for item in self.imports}
        fpga_devices = {
            ref
            for item in self.imports
            if item.kind == "fpga-production"
            for ref in item.extracted.parts
        }
        for operation in self.operations:
            if operation.programs and operation.kind != "programming":
                raise ValueError(f"{operation.id} programs FPGA devices but is not programming")
            if len(set(operation.programs)) != len(operation.programs):
                raise ValueError(f"{operation.id} lists an FPGA device twice")
            for ref in operation.programs:
                if ref not in fpga_devices:
                    raise ValueError(
                        f"{operation.id} programs {ref!r}, which no fpga-production import provides"
                    )
        for characteristic in self.characteristics:
            for source in characteristic.sources:
                if source not in requirements and not (
                    source.startswith("import:") and source.removeprefix("import:") in imports
                ):
                    raise ValueError(f"{characteristic.id} has unresolved source {source!r}")
        for inspection in self.inspections:
            if inspection.characteristic not in characteristics:
                raise ValueError(
                    f"{inspection.id} references unknown characteristic {inspection.characteristic}"
                )
            if inspection.operation not in operations:
                raise ValueError(
                    f"{inspection.id} references unknown operation {inspection.operation}"
                )
            for command_id in inspection.ftm_commands:
                if command_id not in commands:
                    raise ValueError(f"{inspection.id} references unknown FTM command {command_id}")
        for failure_mode in self.failure_modes:
            if failure_mode.operation not in operations:
                raise ValueError(
                    f"{failure_mode.id} references unknown operation {failure_mode.operation}"
                )
            for inspection_id in failure_mode.controls:
                if inspection_id not in inspections:
                    raise ValueError(
                        f"{failure_mode.id} references unknown inspection {inspection_id}"
                    )
        if self.factory_test_mode:
            for command in self.factory_test_mode.commands:
                for characteristic_id in command.covers:
                    if characteristic_id not in characteristics:
                        raise ValueError(
                            f"{command.id} references unknown characteristic {characteristic_id}"
                        )
        if not self.factory_test_mode and any(item.ftm_commands for item in self.inspections):
            raise ValueError("ftm_commands require factory_test_mode")
        return self


def load_contract(path: Path | str) -> ProdengContract:
    contract_path = Path(path)
    try:
        payload = json.loads(contract_path.read_text(encoding="utf-8"))
        return ProdengContract.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"could not load contract {contract_path}: {exc}") from exc


def contract_json(contract: ProdengContract) -> str:
    return json.dumps(contract.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
