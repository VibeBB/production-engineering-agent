# MCP tools

The prodeng MCP server exposes the tools below. `readOnlyHint` is false for
tools that write or modify workspace files; all tools declare
`destructiveHint: false`, `idempotentHint: true`, and `openWorldHint: false`.
Inputs containing workspace paths are resolved and constrained by the
workspace path helper.

| Tool | Access | Input summary | Output |
| --- | --- | --- | --- |
| `prodeng_record_decision` | Write | `DecisionInput`: slug ID/stage, question, principles, at least two named options with pros/cons, chosen option, rationale, assumptions, unknowns, risks, revisit trigger, author, and file/reference evidence. | Appends a VRP decision and returns its event reference. |
| `prodeng_record_impression` | Write | `StageImpressionInput`: stage slug, one or more workspace artifacts, and a 400+ character, three-sentence impression. | Appends a SHA-bound stage impression and returns its event reference. |
| `prodeng_record_vision_review` | Write | `VisionReviewInput`: image path or source event ID, model, checklist slug, findings (`info`, `warning`, or `error`), and long-form impression. | Appends an image-bound vision review and returns its event reference. |
| `prodeng_records_status` | Read | No arguments. | Record counts and last Stop-hook status. |
| `prodeng_ux_inbox` | Read | No arguments. | UX-creator SLP v2 requests for prodeng, states, counts, and malformed-file details. |
| `prodeng_ux_respond` | Write | `UxRespondInput`: request ID, status/reason, artifact paths, optional gate verdicts and contract path, VRP references, and user questions. | Validates and atomically writes `liaison/<id>.ux-response.json`. |
| `prodeng_doctor` | Read | No arguments. | Package, Python, and tools-image diagnostics. |
| `prodeng_validate` | Read | `contract_path`. | Contract validation result and product identity. |
| `prodeng_gates` | Read | `contract_path`. | Deterministic checks and pass/fail/unknown verdict. |
| `prodeng_export` | Write | `contract_path`; optional `out_dir`. | Writes projections and returns their paths. |
| `prodeng_author` | Write | `contract_path`; optional `out_dir`; `render` boolean defaults to `true`. | Runs gates, writes projections, report, and requests; when rendering, includes required image paths and next-step guidance. |
| `prodeng_render` | Write | `contract_path`; optional `out_dir`. | Writes PNG sheets and index and returns image paths and vision-review guidance. |
| `prodeng_import` | Write | `contract_path`, `kind`, and `file`. Kinds: `circuit-brief`, `circuit-connectivity`, `mech-envelope`, `wire-contract`, `ux-contract`, `fpga-production`, `firmware-production`. | Rewrites the contract with extracted data and SHA-256 provenance. |
| `prodeng_requests` | Write | `contract_path`; optional `out_dir`. | Derives outbound v2 request files and returns their paths. |
| `prodeng_liaison` | Read | `directory`. | Reconciles prodeng request/response files; reports entries, orphans, and malformed files. |
| `prodeng_sample` | Read | `lot`, `aql`, optional level (default `II`). | Attribute sampling plan values. |

The decision, impression, vision-review, and UX-response inputs are generated
from strict Pydantic models in `src/prodeng/records.py` and
`src/prodeng/ux_liaison.py`; consult those models for the complete JSON
Schema, required fields, and field constraints.

## Inline images

`prodeng_render` and `prodeng_author` return JSON text first. For each
existing PNG path listed in `vision_review_required`, the MCP call result
then includes one `ImageContent` block with MIME type `image/png` and
base64-encoded bytes. CLI commands write files but do not return inline
images. `prodeng_author` renders by default over MCP; its `render: false`
option omits images. The CLI `author` command renders only with `--render`.

Image content is presentation data. It does not change the text payload's
gate verdict or record a VRP review by itself.
