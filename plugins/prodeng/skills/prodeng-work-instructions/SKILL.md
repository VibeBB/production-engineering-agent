---
name: prodeng-work-instructions
description: Write safe, traceable production work instructions in the Toyota Training Within Industry Job Instruction format.
version: 0.1.0
license: BSD-3-Clause
triggers:
  - work instruction
  - job instruction
  - standard work
  - assembly instructions
---

# Work instructions

The contract's `operations[].work_elements[]` are the source for the
generated `work-instructions.md`. For each operation, write each work
element as a TWI Job Instruction table:

| Major step | Key points | Reasons |
| --- | --- | --- |

Use the exact operation/process order. One major step describes a meaningful
chunk of work; key points state how to do it safely and correctly; reasons
explain quality, safety, ergonomic, or process significance. Every step
needs at least one key point or the work-instruction gate fails.

For each operation document, where applicable:

- **4M context:** Man, Machine, Material, Method — qualification/role,
  equipment and tool, controlled material/lot, and approved method/revision.
- **Tools and fixtures:** identify the tool/fixture and any calibration,
  setup, datum, or verification requirement.
- **ESD:** identify ESD-sensitive work, wrist strap/grounding checks,
  protected area, packaging, and handling controls; follow the facility's
  approved ESD program.
- **Safety:** state hazards, required precautions/PPE/interlocks, and
  stop/escalation response. Hipot and ground-bond operations must declare
  hazards and safeguards. Never instruct bypassing an interlock or working
   on energized exposed circuits.
- **Inspection linkage:** cite the linked `IN-##` checks at the step where
  the operator performs or records them; include acceptance, reaction,
  containment, and traceability references from the approved control plan.

Do not invent process parameters, work acceptance limits, rework criteria,
or equipment calibration intervals. Request missing controlled values from
the process/product owner.

The document sibling owns controlled document styling, revision history,
released work-instruction numbering, translation, and document release.
Production engineering supplies the structured steps, key points, reasons,
operation/inspection links, and safety content as a document-sibling
request; it does not release a controlled document itself.

## Vision review points

After every `prodeng_author` that renders or `prodeng_render`, inspect each
returned PNG (inline, with `file_editor view`, or with
`inspect_image_with_vision` using the `vibebb-review` profile). Record one
`prodeng_record_vision_review` per image; use `work-instruction` for TWI
sheets and the matching `control-plan`, `pfmea`, `line-balance`, or
`factory-test-spec` checklist for other production sheets. Judge contract
accuracy, ambiguity, design intent, and whether an operator or inspector can
act on the content. Review intake photos in `intake/attachments/` with
`intake-photo` and sibling circuit/PCB/schematic or mechanical drawings with
`sister-render`.
