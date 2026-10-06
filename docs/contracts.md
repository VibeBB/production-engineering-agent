# Contracts and generated artifacts

## Source contract

`*.prodeng.json` is a frozen Pydantic v2 model with
`schema_version: 1` and `system: "prodeng"`. Unknown fields are rejected.
Its top-level fields are:

| Field | Contents |
| --- | --- |
| `product` | Lowercase product slug, revision, optional description. |
| `volume` | Annual demand, working days, shifts, available minutes per shift, lot size; takt is derived from these values. |
| `requirements` | Requirement, assumption, and question records with IDs, text, kind, and open/resolved status. |
| `characteristics` | Product characteristics with classification, variable/attribute kind, measurement limits or acceptance criterion, unit, sources, and an optional `simulation` prediction (`report_path`, `sha256`, `check_id` of a simulation-agent `sim-report.json` check; variable characteristics only). |
| `operations` | Ordered process operations with station, cycle time, operators, tools/fixtures, safety data, and TWI work elements. |
| `inspections` | Characteristic and operation links, inspection method, sampling, equipment, reaction plan, and optional FTM command references. |
| `failure_modes` | PFMEA operation, mode/effect/cause, severity/occurrence/detection scores, and linked controls. |
| `factory_test_mode` | Optional entry conditions, field lockout, interface/nets, commands/timeouts, provisioning, exit, and duration budget. |
| `imports` | Supported sibling source kind, relative path, SHA-256, and extracted nets/parts/connectors/anchors/surfaces. |

Model validators enforce ID prefixes, references, mutually consistent
limits, required characteristic inputs, valid AQL/levels, and FTM
relationships. The gate implementation adds runtime checks such as
inspection coverage, station takt, import freshness, PFMEA controls, and
work-instruction safety.

## Outbound prodeng request v2

Files matching `*.prodeng-request.json` use schema version 2 and
`system: "prodeng"`. Each contains a target agent, topic, risk, rationale,
declared characteristic/inspection/requirement citations, requested changes,
and one or more `{path, sha256}` input references. High-risk requests must
cite at least one declared characteristic, requirement, or inspection ID.
The schema recognizes `circuit`, `firmware`,
`fpga`, `mech`, `wire`, `ux`, `doc`, `dashboard`, `sim`, and `bard`; automatic
derivation currently emits only targets supported by `derive_requests()`.

## Sibling response v2

Files matching `*.prodeng-response.json` use `system: "prodeng"`,
`schema_version: 2`, the request name, responder, status (`accepted`,
`rejected`, `deferred`, or `needs_info`), reason, artifact path/hash pairs,
input hashes, and decision references. The liaison reader marks a reply
stale when its input hashes no longer match the request and mismatched when
the responder differs from the target agent. A response is informational;
it does not change a gate result.

## UX-creator SLP v2

Inbound `liaison/<id>.ux-request.json` files use
`schema_version: 2`, `system: "ux-creator"`, matching ID/file stem,
target agent, stage, risk, purpose, rationale, requested changes, SHA-bound
inputs, expected deliverables, acceptance criteria, dependencies, and
timestamp. Strict validation rejects unknown fields; high-risk rationales
must cite a recognized UX job ID.

Prodeng writes `liaison/<id>.ux-response.json` with request/responder/status,
reason, current input hashes, artifact hashes, gate verdicts, decision and
impression references, user questions, and response time. `done` requires
artifacts, passing gate verdicts, and valid VRP references. Responses are
written atomically. Inbox state detects malformed and stale files, waits
for dependencies with `done` responses, and otherwise reports new or
answered requests. See [Sister cooperation](sister-cooperation.md).

## Render index

`out/<product>/renders/index.json` is deterministic and has
`schema_version`, `product`, the selected `font` filename (or
`pillow-default`), and sorted render entries. Each entry identifies the
sheet name, path relative to the output directory, PNG SHA-256, projection
source filename, and source SHA-256. No timestamp is written.

## VRP records

VRP v1 appends `decision`, `stage_impression`, and `vision_review` events to
`observations/prodeng/decisions.jsonl`,
`observations/prodeng/impressions.jsonl`, and
`observations/prodeng/vision-reviews.jsonl`. Each event has schema version,
plugin name, sequence, event ID, and recorded time. Required fields and
writer behavior are detailed in [Records and vision](records-and-vision.md).

## `out/<product>/` projections

`prodeng_export` and `prodeng_author` generate:

- `control-plan.csv`
- `inspection-plan.json`
- `sampling-plans.json`
- `line-balance.csv`
- `pfmea.csv`
- `work-instructions.md`
- `factory-test-spec.json` and `factory-test-spec.md`
- `manifest.json` and `provenance.json`
- With `prodeng_author`: `prodeng-report.json` and `prodeng-report.md`
- With rendering enabled: `renders/*.png` and `renders/index.json`

These artifacts are projections, not editable sources. Regenerate them from
the contract. `author` also writes outbound request files beside the
contract; those are not placed under `out/` by default.
