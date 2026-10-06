---
name: prodeng-contract
description: Author and inspect the production-engineering source-of-truth JSON contract.
version: 0.1.0
license: BSD-3-Clause
triggers:
  - prodeng contract
  - production contract
  - manufacturing contract
  - factory-test-mode contract
---

# Contract authoring

Use `examples/smart-kettle/smart-kettle.prodeng.json` as the complete
reference contract. The schema is Pydantic v2, frozen, and rejects unknown
fields. It follows the load-time contract in PLAN §3. The system is
`prodeng`; do not encode operational facts only in generated CSV, Markdown,
or request files.

| Field | Required shape and authoring rule |
| --- | --- |
| `schema_version`, `system` | Use `1` and `"prodeng"`. |
| `product` | `name` is lowercase letters/digits/hyphens and starts alphanumeric; include non-empty `revision`; `description` is optional. |
| `volume` | Positive annual demand, working days/year, shifts/day, and available minutes/shift; `lot_size >= 2`. `takt_s = working_days_per_year * shifts_per_day * available_minutes_per_shift * 60 / annual_demand_units`. |
| `requirements` | IDs match `R<n>`, `A<n>`, or `Q<n>`; kinds are requirement, assumption, or question and must agree with the prefix. Status is `open` or `resolved`; only `Q` status drives the open-question gate. Keep requirement text evidence-based. |
| `characteristics` | IDs `CH-##`; description, classification (`critical`, `major`, `minor`), and kind (`variable`, `attribute`). Variable characteristics require a unit and at least one limit; enforce `lsl <= nominal <= usl` wherever values exist. Attribute characteristics need a non-empty acceptance criterion. Every source references an existing requirement or `import:<system>` backed by a matching import. |
| `operations` | IDs `OP##`; process kind is `smt`, `tht`, `selective_solder`, `harness`, `mechanical_assembly`, `programming`, `test`, `inspection`, `packing`, or `other`. Give station, positive cycle time in seconds or explicit `null`, and a non-negative operator count. Add tools, fixtures, ESD sensitivity, hazards, precautions, and work elements as applicable. Each work element contains a major step, key points, and reasons. A `programming` operation lists the FPGA device references it loads in `programs`; each must come from an `fpga-production` import. |
| `inspections` | IDs `IN-##`; link one characteristic and operation. Method is `visual`, `spi`, `aoi`, `axi`, `ict`, `flying_probe`, `boundary_scan`, `fct`, `hipot`, `ground_bond`, `measurement`, or `burn_in`. Provide equipment and a non-empty reaction plan; sampling is `{mode: "full"}` or `{mode: "aql", aql, level}`, with AQL from the supported values and level I/II/III/S-1/S-2/S-3/S-4 (default II). Reference FTM commands only when declared. |
| `failure_modes` | IDs `FM-##`; link an operation and inspection controls; state mode, effect, cause, and integer 1–10 severity/occurrence/detection ratings. A severity of 9 or 10 requires at least one full-inspection control. |
| `factory_test_mode` | Optional object with entry method (`gpio_strap`, `uart_magic`, `button_combo`, `test_pad`, `jtag_swd`, or `other`), detail/conditions, field lockout (`otp_fuse`, `nvm_flag`, `signed_token`, `physical_removal`, or `none`), interface, fixed commands, provisioning, exit, and positive maximum duration. Require at least two independent entry conditions. Each command has a unique `TC-##`, request/response pattern, positive timeout, measured nets/characteristics, and destructive flag. |
| `imports` | System is `circuit`, `mech`, `wire`, `ux`, or `fpga`. Record kind, source path, lowercase SHA-256 digest, and normalized extracted nets/parts/connectors/anchors/surfaces. Paths are resolved relative to the contract file for freshness checks. |

## Load-time relationships

IDs are unique within their collection. Every inspection characteristic,
operation, and FTM command reference must resolve; failure-mode operation
and control references must resolve; command `covers` IDs must resolve to
characteristics; and imported characteristic sources need a corresponding
import record. Non-empty `ftm_commands` requires a declared
`factory_test_mode`. These are schema/load errors, not gates: fix the
contract before exporting.

Keep requirements traceable to drawings, standards, certification records,
or sibling artifacts. Do not invent a mains-safety limit to fill a missing
source; record a question and obtain an approved value.
