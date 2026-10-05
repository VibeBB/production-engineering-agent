---
name: prodeng-inspection
description: Classify product characteristics, design inspection coverage, and use ISO 2859-1 sampling conservatively.
version: 0.1.0
license: BSD-3-Clause
triggers:
  - inspection plan
  - sampling plan
  - AQL
  - critical characteristic
  - end-of-line test
---

# Inspection and sampling

When operating through the plugin, use its `prodeng_*` MCP tools. The MCP
server uses the installed Docker-only launcher; do not run the host package
as a fallback.

## Characteristic class and coverage

- **Critical** characteristics affect safety, regulatory compliance, or
  another explicitly designated critical function. Link an inspection with
  `sampling: {mode: "full"}` (100% coverage). The model does not decide that
  a safety characteristic is noncritical to avoid full inspection.
- **Major** and **minor** characteristics may use AQL sampling where the
  risk analysis and customer/product control plan permit it. Typical
  starting guidance is major AQL 0.65–1.0 and minor AQL 1.5–4.0; these are
  not universal acceptance requirements.
- Use the deterministic `sample --lot N --aql X [--level II]` CLI command.
  General inspection levels are I, II, and III;
  special levels are S-1 through S-4. Use the level and AQL specified by
  the approved control plan, contract, or customer agreement. ISO 2859-1
  and JIS Z 9015-1 are the sampling references; do not substitute an
  approximate sample count.

## Method placement

Select methods that match the characteristic and process station:

- **SPI** checks solder-paste volume/position after printing; **AOI** checks
  visible assembly features after SMT/reflow; **AXI** checks hidden solder
  joints where applicable.
- **ICT** and **flying probe** check electrical nets/components; **boundary
  scan** uses the IEEE 1149.1 access architecture when implemented.
- **FCT** verifies assembled product behavior at programming/final test.
  Its factory-test commands must be declared and fit the station time.
- **Hipot** verifies dielectric withstand; **ground bond** verifies
  protective-earth continuity/bond resistance. They are distinct tests and
  must link to distinct, appropriate characteristics.
- **Burn-in** is a controlled reliability screen when required by the
  product/customer plan; document the profile and reaction.

Every inspection has equipment and a reaction plan: identify the affected
lot, contain product since the last known-good point, stop/escalate as
defined, disposition/rework through approved procedures, and record
traceability. Do not invent rework acceptance.

For workmanship references, use the applicable revision/customer
requirements of IPC-A-610 (electronic assemblies), IPC/WHMA-A-620 (cable
and wire harness assemblies), and J-STD-001 (soldered electrical and
electronic assemblies).

Mains products may need routine electric-strength/hipot and earth-bond
tests. IEC 60335-1 Annex A and IEC 62368-1 are example reference families;
which standard applies depends on the product. **Exact test voltages,
durations, leakage limits, and bond limits must come from the applicable
standard and the product's certification procedure, not from the agent.**
Capture the approved source and its revision in a requirement/criterion.

## Vision review points

After every `prodeng_author` that renders or `prodeng_render`, inspect every
returned PNG and record one `prodeng_record_vision_review` per image. Use
`control-plan`, `pfmea`, `line-balance`, `work-instruction`, or
`factory-test-spec` to match the sheet. Judge accuracy against the contract,
ambiguity, design intent, and whether an operator or inspector can act on it.
Review intake photos in `intake/attachments/` with `intake-photo` and sibling
circuit/PCB/schematic or mechanical drawings with `sister-render`.
