# Production-engineering workflow

The authored `*.prodeng.json` contract is the source of truth. The
deterministic core validates it, evaluates gates, writes projections, and
derives workspace JSON for sister plugins. Agent reasoning and image review
can explain risks or request changes, but cannot change a gate verdict.

| Stage | Work and tools | Records to leave |
| --- | --- | --- |
| Intake | Gather approved requirements, annual demand, shift calendar, lot size, product safety inputs, existing process knowledge, and optional imports/photos. Use `prodeng_import` for supported JSON artifacts; attachment hooks may materialize user images in `intake/attachments/`. | Record important assumptions and choices with `prodeng_record_decision`; finish the stage with a bound `stage_impression`. |
| Contract | Author and validate the frozen `*.prodeng.json` schema. Resolve requirement, characteristic, operation, inspection, PFMEA, FTM, and import references. Use `prodeng_validate` or `prodeng validate`. | Record design choices and unresolved assumptions; finish with an impression bound to the contract and supporting artifacts. |
| Gates | Run `prodeng_gates` or `prodeng gates`. Deterministic checks return pass, fail, or unknown. Resolve missing evidence at its source; never promote unknown to pass. | Preserve the gate report and record a stage impression that names failed or unknown checks. |
| Projections | Run `prodeng_author` or `prodeng_export` to write control-plan, inspection and sampling, line-balance, PFMEA, TWI work-instruction, FTM, provenance, and manifest artifacts. `prodeng_author` additionally writes the report and derives outbound requests. | Record decisions about takt, operation allocation, inspection and AQL, PFMEA ratings, poka-yoke, fixtures, test access, FTM safeguards, and request risk. Finish after the final regeneration. |
| Vision review | Inspect every PNG returned by MCP author/render or written under `out/<product>/renders/`. Use inline MCP images, `file_editor view`, or the configured vision tool. Review relevant intake photos and sister-plugin drawings as well. | Write one `prodeng_record_vision_review` per image, bound to the image path or a vision event. Use the checklist slug for the image type and a 400+ character impression. |
| Liaison | Derive outbound `*.prodeng-request.json` files and reconcile `*.prodeng-response.json` files with `prodeng_liaison`. Separately, read UX-creator requests with `prodeng_ux_inbox` and answer them with `prodeng_ux_respond`. | Record request-risk choices and important response decisions; finish the stage with an impression bound to the requests, replies, and current contract. |
| Handoff | Present the deterministic report, generated files, open/answered/stale/malformed liaison states, image-review findings, assumptions, and remaining work. Do not imply certification or process approval. | Leave a final `handoff` stage impression bound to the delivered artifacts. The Stop hook checks required records. |

## Record rules

Each decision records first-principles or standards-based principles, at
least two options, the chosen option, a substantive rationale, evidence,
assumptions, unknowns, risks, and a revisit trigger. File evidence is
SHA-256-bound; non-file evidence cites a reference. Stage impressions require
at least 400 characters and three distinct sentences. Vision reviews require
an image path or source-event ID and the same long-form impression rule.

The expected stages are `intake`, `contract`, `gates`, `projections`,
`vision-review`, `liaison`, and `handoff`. Append records through the writer
tools rather than editing JSONL files. Full schemas and hook enforcement are
documented in [Records and vision](records-and-vision.md) and [Hooks](hooks.md).
