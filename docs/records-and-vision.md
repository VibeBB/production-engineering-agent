# Records and vision review

## VRP v1

The plugin uses the shared VibeBB Record Protocol v1. Three append-only
JSONL logs live under `observations/prodeng/`:

- `decisions.jsonl` records why a non-trivial choice was made.
- `impressions.jsonl` records an end-of-stage reflection bound to final
  artifacts.
- `vision-reviews.jsonl` records what was observed in an image and binds
  the review to an image or vision event.

Every entry has `schema_version: 1`, `plugin: "prodeng"`, a sequence number,
SHA-256 event ID, and `recorded_at`. Use the MCP record tools or CLI
`record` subcommands; direct JSONL editing is not the supported writer path.
`prodeng_records_status` reports counts and the last Stop-hook verdict.

### Decision

A decision has a slug ID and stage, a question, first-principles or
standards-based principles, at least two distinct options with pros and
cons, a chosen option, a rationale of at least 200 characters, assumptions,
unknowns, at least one risk, a revisit trigger, an author, and evidence.
Questions need at least 10 characters; principles must each contain at
least 12 characters. Each option needs a unique name plus non-empty pros and
cons, and `chosen` must match one option. Workspace path evidence (a file or
directory) is SHA-256-bound; non-file evidence names a reference.

### Stage impression

A stage impression names its stage, binds to one or more existing files or
directories by SHA-256, and contains at least 400 characters and three
distinct sentences. The prose describes what was noticed, what works, what
is concerning, how the maker or user would interpret the result, and what
to do next.

### Vision review

A vision review binds to an `image_path` or `source_event_id`, records the
model and checklist slug, and may include findings with severity
`info`, `warning`, or `error`. Its impression follows the same 400-character
and three-sentence rule. If an image path is provided, the writer records
its current SHA-256.

## Vision review points

Record one VRP vision review for each inspected image using the matching
checklist slug:

| Image | Checklist slug |
| --- | --- |
| Control-plan render | `control-plan` |
| PFMEA render | `pfmea` |
| Line-balance render | `line-balance` |
| TWI work-instruction render | `work-instruction` |
| Factory-test specification render | `factory-test-spec` |
| User intake photo under `intake/attachments/` | `intake-photo` |
| Sister circuit/PCB/schematic image or mechanical drawing | `sister-render` |

Inspect every image returned by an MCP `prodeng_render` or rendered
`prodeng_author` call, or every PNG written by the CLI. Compare the sheet
with the contract for accuracy, ambiguity, intended design, and whether a
shop-floor operator or inspector could act on it. A vision result is an
advisory observation: it is not a measurement, validation, certification,
or gate verdict.

## Image transport and audit

MCP render/author calls return their JSON `TextContent` first and then one
`ImageContent` block per existing PNG. Each image block is base64-encoded
with MIME type `image/png`. The CLI writes PNG files and does not return
inline blocks. A call's image list does not itself create a VRP review.

The post-tool `record-vision-tool-event` hook hashes successful
`inspect_image_with_vision` answers into
`observations/prodeng/vision-tool-events.jsonl`. The
`record-image-observation` hook records image paths and byte hashes from
direct views or successful render/author/terminal responses in
`observations/prodeng/image-observations.jsonl`. These provenance logs are
additional observation data, not substitutes for the three VRP event logs.

The record Stop hook enforces record completeness according to
`records-policy.json`; records never feed gate calculations. See
[Hooks](hooks.md) and [Contracts](contracts.md) for schema and policy.
