# Architecture

This document describes the implementation layers. See the
[documentation index](README.md) for the workflow, interfaces, records, and
operations guides.

## Three layers

| Layer | Location | Responsibility |
| --- | --- | --- |
| L1 — Deterministic core | `src/prodeng/` | Contract parsing/validation, gates, sampling, imports, projections, requests/responses, reports, CLI, and MCP boundary. Sole pass/fail authority. |
| L2 — OpenHands plugin | `plugins/prodeng/` | Skills, agent prompts, commands, hooks, and launcher steer workflows and invoke deterministic CLI operations. LLM judgment is advisory. |
| L3 — Observation records | `src/prodeng/records.py`, `plugins/prodeng/hooks/scripts/`, and workspace `observations/prodeng/` | Append decision, stage-impression, and vision-review records with provenance; records are not gate inputs. |

The `*.prodeng.json` contract is truth. `out/<product>/` and
`*.prodeng-request.json` are projections and are never hand-edited.
`unknown` fails closed. Sibling agents exchange workspace JSON plus
SHA-256 provenance and use `task_tool_set` delegation; no sibling package
is imported.
The launcher runs only in the digest-locked
`ghcr.io/vibebb/prodeng-tools` image and has no host fallback.

## Deterministic gates

The verdict is pass only when every emitted check passes. A failed check
produces fail; with no failures, any unknown produces unknown.

| Check ID | Subject | Rule |
| --- | --- | --- |
| `coverage.characteristic` | Characteristic | At least one linked inspection. |
| `coverage.critical_full` | Critical characteristic | At least one linked full inspection. |
| `sampling.plan` | AQL inspection | ISO 2859-1 plan resolves; otherwise unknown. |
| `takt.station` | Station | Sum of operation cycle times is at most takt; null time is unknown. |
| `ftm.present` | Product | If any inspection is FCT, an FTM declaration exists. |
| `ftm.entry_guard` | FTM | At least two entry conditions. |
| `ftm.lockout` | FTM | Field lockout method is not `none`. |
| `ftm.duration` | FTM | Sum of command timeouts is at most the FTM duration budget. |
| `ftm.station_fit` | FTM operation | Timeouts used by inspections at the operation fit cycle time; null time is unknown. |
| `ftm.command_used` | FTM command | Covers at least one characteristic and is linked to an inspection. |
| `dft.test_access` | Test net | Each FTM interface/measurement net is present in extracted circuit nets; a missing net fails, and no circuit import is unknown. |
| `pfmea.controls` | Failure mode | At least one inspection control is linked. |
| `pfmea.high_severity` | Severity ≥ 9 failure mode | At least one linked control is a full inspection. |
| `work_instruction.steps` | Operation | At least one work element exists and each has a key point. |
| `work_instruction.safety` | Operation | Hazards have precautions; hipot/ground-bond operation declares hazards. |
| `imports.fresh` | Import | Source exists and SHA-256 matches; a mismatch fails, and a missing source is unknown. |
| `firmware.programming` | MCU | A `programming` operation lists the MCU in `programs`, the ELF still has the gated SHA-256 and size, and the firmware was gated against the current `factory-test-spec.json` and its command ids (or neither side declares a factory test mode); an unreadable artifact or ELF is unknown. |
| `fpga.programming` | FPGA device | A `programming` operation lists the device in `programs`, the target is `flash`, and the bitstream still has the gated SHA-256 and size; an unreadable artifact or bitstream is unknown. |
| `requirements.open_questions` | Open question | Open `Q` requirement is unknown. |

`ftm.present` is emitted only when an FCT inspection exists. Sampling plans
are required for AQL inspections; full inspections do not need an AQL
resolution. PFMEA RPN is informational and does not replace severity gates.

## Artifact flow

1. Validate authored JSON using the frozen Pydantic schema and
   load-time cross-reference rules.
2. Run gates using the contract and its containing directory (for import
   freshness).
3. Export control plan, inspection/sampling plans, line balance, PFMEA,
   work instructions, FTM specifications, manifest, provenance, and report.
4. Derive one or more deterministic sibling request files. Reconcile
   response files for informational status only.

Outputs use stable ordering, UTF-8, a final newline, and no generated
timestamps. See [ADR-0001](adr/0001-deterministic-core-and-gates.md) and
[ADR-0003](adr/0003-sibling-cooperation-via-contracts.md).

## Render and liaison boundaries

`src/prodeng/render.py` produces contract-derived PNG sheets and a
`renders/index.json` containing image and source hashes. MCP render/author
responses can carry PNG `ImageContent` blocks after the JSON text result.
Rendered images and vision observations are advisory views, not gate inputs.

Outbound prodeng requests and sibling responses use schema version 2 and
input hashes. Inbound UX-creator requests and prodeng replies use the SLP v2
schema under `liaison/`. Liaison state and record completeness are
informational/enforcement workflows separate from the deterministic gate
verdict. See [Contracts](contracts.md), [MCP](mcp.md), and
[Records and vision](records-and-vision.md).
