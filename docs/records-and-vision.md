# Records and vision review

## VRP v2

The plugin uses the shared VibeBB Record Protocol v2 (wire-agent is the
family reference; [ADR-0010](adr/0010-vrp-v2-records.md)). Append-only JSONL
logs live under `observations/prodeng/`:

| Log | Record kind |
| --- | --- |
| `decisions.jsonl` | `decision` — why a non-trivial choice was made |
| `impressions.jsonl` | `stage_impression` — grounded end-of-stage reflection |
| `vision-reviews.jsonl` | `vision_review` — what an image shows, per reviewer role |
| `reconciles.jsonl` | `review_reconcile` — primary/blind/tiebreak outcome |
| `insights.jsonl` | `insight_status` — adopt/reject/defer/dispute an idea or concern |
| `song-receipts.jsonl` | `song_receipt` — one-time receipt of a bard song |
| `reads.jsonl` | `upstream_read` — read receipt for a sister impression |

Every entry has `schema_version: 2`, `plugin: "prodeng"`, a sequence number,
`prev_event_id` linking it to the previous entry, and an `event_id` derived
from the SHA-256 of the canonical record. Each writer verifies the whole
chain before appending: an edited, deleted, truncated, reordered or
malformed line fails closed. v1 logs are archived as `<name>.v1.jsonl` on the
first v2 write. Use the MCP record tools or `python -m prodeng record <kind>`;
direct JSONL editing is blocked by `protect-generated`.

### Decision

A decision has a slug ID and stage, a question, principles, at least two
distinct options with pros and cons, a chosen option, a rationale of at least
200 characters, assumptions, unknowns, risks, a revisit trigger, an author,
and SHA-256-bound evidence.

### Stage impression

A stage impression binds to existing artifacts by SHA-256 and needs 400+
characters in three or more sentences plus structured `facets` (`observed`,
`works`, `concerns`, `feelings` for maker and user, `next_actions`),
`claims` that quote an exact token found in a bound artifact, a
`confidence`, and `unknowns`. Every sister impression the author took in must
appear in `upstream` with a matching read receipt. A near-duplicate of an
earlier impression, or a concern re-raised after it was disputed or resolved
without new evidence, is refused.

### Vision review

A vision review binds to an `image_path` (SHA-256) or `source_event_id`,
names the model, checklist slug and `reviewer` role (`primary`, `blind` or
`tiebreak`), and carries findings, facets, claims, `confidence` and a
`lookback` entry per claim. Production renders (`**/renders/*.png`) are
dual-review images: `prodeng-blind-review` records the blind round behind the
`blind-guard` hook, and `prodeng_record_reconcile` closes round 1 when the
two agree. A split calls a round-2 `tiebreak`; a split after round 2 stays
`unknown`. Reviews never become gate verdicts.

### Insights, reads and songs

`insight` records the lifecycle of an idea or concern from any record
(`adopted`, `rejected`, `deferred`, `disputed`, `resolved`) with a rationale.
`read` writes a receipt for a sister impression found through
`prodeng_records_search` / `prodeng_records_digest`. prodeng only receives
bard songs: `song-receipt` pins `liaison/<id>.bard-song.json` by SHA-256,
is allowed once per song, and never requests another song.

`prodeng_records_status` reports counts and the last Stop-hook verdict.

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
additional observation data, not substitutes for the VRP event logs.

The record Stop hook enforces record completeness according to
`records-policy.json`; records never feed gate calculations. See
[Hooks](hooks.md) and [Contracts](contracts.md) for schema and policy.

## Session-scoped Stop status

The Stop hook excludes a record with an explicit different session ID,
even when its timestamp is recent. Legacy records without an ID are
eligible only from the session start through the following 24 hours;
their use is reported as an attribution warning. Missing session
identity or a missing start marker also leaves attribution unverified.
Reviews bind both the resolved image path and its SHA-256; an event ID
cannot substitute for that binding. Supply an explicit `image_path` to
the review writer so it records the current bytes. Legacy reference-only
reviews remain readable but do not discharge image-review obligations.

Stop writes `observations/<plugin>/records-status.json` and a
`observations/<plugin>/.sessions/<session>.status.json` snapshot:

| Field | Meaning |
| --- | --- |
| `stop_permission` | `deny` while the configured refusal budget remains, then `allow` |
| `record_compliance` | `fail` for missing evidence, `unknown` for attribution warnings, otherwise `pass` |
| `run_completion` | `unknown`; only the execution workflow can establish completion |
| `acceptance` | `unknown`; only the product acceptance workflow can establish it |
| `checkpoint` | Session marker containing the start time and refusal count |

An exhausted refusal budget permits termination while preserving the
unresolved problems. The compatibility `verdict` describes the hook's
problem list only; consumers must use the explicit fields above and must
not infer product acceptance from Stop permission or the absence of
record problems. Reviewer identity propagation and derived-image
ownership require a separate recording contract; this status does not
claim to verify them.

## Session attribution

Pass the native `session_id` from the SessionStart record context in record-tool
inputs. The writer also accepts `OPENHANDS_SESSION_ID` when supplied by the SDK
process; conflicting explicit and environment identities are rejected. The ID is
included in the record hash. Writers never infer it from shared marker files.

Delegated SessionStart hooks expose only native record context (`record-context`), without
recalling earlier review prose. Ordinary plugin SessionStart retains sister-concern recall.

Delegate independent reviews with an opaque `primary_event_id`, the resolved image
path and SHA-256; never send the earlier findings. Reviewers keep their own native
`session_id`. The writer and Stop resolve that reference into an intact primary
with the same plugin, path and hash and a different native session. Every review
role has its own session. Reconciliation belongs to the primary's session.

A copied image has its own round. Historical inputs without identity remain
supported, with bounded timestamp attribution and an unknown compliance warning
at Stop; they cannot satisfy explicitly scoped writer rounds.

Stop permission, record compliance, run completion and acceptance are separate
status fields. Reaching the refusal budget permits stopping while preserving gaps;
it does not establish execution completion or product acceptance.
