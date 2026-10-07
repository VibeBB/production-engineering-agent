# Skills

All nine skills are installed under `plugins/prodeng/skills/`. They provide
workflow guidance; the contract schema, deterministic code, and hook policy
remain authoritative.

| Skill | Purpose |
| --- | --- |
| `prodeng-contract` | Author and inspect the production-engineering source-of-truth contract, including its field shapes and cross-references. |
| `prodeng-contract-rules` | Apply path-scoped validation rules to `*.prodeng.json` files. |
| `prodeng-dfx` | Review circuit, mechanical, and wire artifacts for manufacturability, assembly, and testability; suggest evidence-backed sibling requests. |
| `prodeng-factory-test-mode` | Specify guarded FTM entry, field lockout, bounded commands, provisioning, and ownership boundaries. |
| `prodeng-inspection` | Classify characteristics, design inspection coverage, and use supported ISO 2859-1 sampling conservatively. |
| `prodeng-liaison` | Answer UX-creator requests and reconcile versioned sister requests and responses. |
| `prodeng-out-rules` | Path rule on `**/out/**`: generated artifacts are read-only projections — change the contract and regenerate (the `protect-generated` hook enforces). |
| `prodeng-work-instructions` | Author safe, traceable TWI Job Instruction work elements in the contract. |
| `prodeng-workflow` | Run the end-to-end workflow from intake and contract authoring through gates, projections, visual review, liaison, and handoff. |

The skills share these boundaries:

- Generated projections and request files are regenerated from the contract,
  not edited by hand.
- LLM and vision observations are advisory and do not alter gate verdicts.
- Plugin operations use the configured `prodeng_*` MCP tools and Docker-only
  launcher; a missing image lock is a blocker, not a reason to run on the
  host.
- Visual-review guidance requires reviewing every rendered production sheet
  and recording an image-bound VRP vision review. It also identifies intake
  photos (`intake-photo`) and sister circuit/PCB/schematic or mechanical
  drawings (`sister-render`) as review points.

Agent prompts reference these skill files directly; the plugin does not
declare a `skills:` field in its agent definitions.
