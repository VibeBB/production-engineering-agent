---
name: prodeng-dfx
description: Review circuit, mechanical, and wire artifacts for manufacturability, assembly, and testability and derive advisory sibling requests.
version: 0.1.0
license: BSD-3-Clause
triggers:
  - DFM
  - DFA
  - DFT
  - design for manufacturability
  - design for test
---

# DFM / DFA / DFT review guidance

Use these checklists to identify evidence-backed risks and create
targeted requests for the design-owning sibling. They are review guidance,
not deterministic gate criteria or gate verdicts. State the artifact,
location/net/part/feature, likely production impact, and a testable
suggestion; do not modify sibling source files.

## Circuit

- Confirm fiducials, panelization rails/tooling holes, board outline,
  depanelization, and panel array are compatible with the assembler.
- Check component orientation consistency, polarity marking visibility,
  reference designators, package availability, and one-sided SMT preference
  where it reduces handling/reflow complexity.
- Review solder-mask/paste openings, fine-pitch access, thermal relief, and
  component spacing with the selected assembly process.
- Check test-point reachability, probe side, fixture datum, clearance, and
  net naming. A pad diameter around 1 mm or larger and adequate spacing are
  useful starting points only; the fixture vendor, probe type, board
  stack-up, and certification constraints set the actual dimensions.
- Check boundary-scan chain access and programming/test connector strategy
  where designed. Request missing ICT/flying-probe/FCT access explicitly.

## Mechanical

- Reduce fastener count and standardize fastener types where strength and
  service requirements permit; review access for the intended driver.
- Look for self-locating, keyed, poka-yoke features; clear insertion
  direction; stack-up control; and top-down assembly with few part flips.
- Identify assembly datum/fixture interfaces, clamping surfaces, part
  retention, and inspection access without cosmetic damage.
- Check cable routing, pinch points, seals, adhesives, and assembly
  sequence against the actual process.

## Wire and harness

- Confirm continuity and required hipot tests are reachable with safe
  fixture access and traceable connector/pin mapping.
- Review connector polarization/keying, mating access, strain relief,
  bend radius, wire routing, and connector latching.
- Check durable, legible wire/connector labels and markings at the assembly
  and service locations; avoid labels hidden after installation.
- Request pinout, test method, safe test limits, and failure reaction from
  the owning design/certification source when missing.

Phrase findings as a proposed design change, fixture request, or evidence
question. The authoritative `prodeng gates` command alone returns a gate
verdict; advisory DFx findings can never promote a failed/unknown gate.
