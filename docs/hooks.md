# Hooks

Plugin-wide lifecycle hooks are declared in
`plugins/prodeng/hooks/hooks.json`. Agent hooks are also declared in each
agent's frontmatter; they do not inherit the plugin-wide configuration.

## Plugin lifecycle hooks

| Event and matcher | Hook | Effect |
| --- | --- | --- |
| `session_start`, `*` | `prodeng-doctor` | Reports package, Python, and tools-image diagnostics and can stop startup when plugin root resolution fails. |
| `session_start`, `*`; `user_prompt_submit`, `*`; `stop`, `*` | `intake-attachments` | Scans available AgentCanvas conversation events for user image blocks, materializes them under `intake/attachments/`, and appends provenance to `manifest.jsonl`. It is idempotent and falls back to manual intake when the event store is unavailable. |
| `session_start`, `*` | `ensure-llm-profiles` | Ensures the configured author/review profiles exist when possible and reports vision capability status. |
| `session_start`, `*` | `require-records` | Loads the prodeng policy and creates the per-session marker used by Stop enforcement. |
| `pre_tool_use`, `file_editor|apply_patch|terminal` | `protect-generated` | Denies manual writes to protected generated outputs, records, and generated request/UX-response files. Views and reads remain allowed. Sister `*.prodeng-response.json` files remain writable. |
| `pre_tool_use`, `terminal` | `safety-rail` | Pattern-matches a denylist of catastrophic filesystem/device/power actions and prohibited Git operations. It is a narrow deterministic rail, not a general shell security analyzer. |
| `stop`, `*` | `require-records` | Validates required VRP records and can deny stopping until the debt is addressed, up to the policy's maximum denials. |
| `stop`, `*` | `report-prodeng-status` | Adds report verdicts and failing/unknown gate IDs as stop context; it does not itself issue a gate verdict. |
| `post_tool_use`, `inspect_image_with_vision` | `record-vision-tool-event` | For successful vision-tool calls with a response, records the answer hash, tool/profile/model metadata, and an event ID. |
| `post_tool_use`, `file_editor|terminal|prodeng_render|prodeng_author` | `record-image-observation` | Finds images actually viewed or named in successful tool responses and records their paths and byte hashes. |

Hooks resolve the plugin root from `PRODENG_PLUGIN_ROOT`, the project plugin
directory, or the supported user plugin-install locations. They do not
silently run a different plugin implementation.

## Agent-declared hooks

- `prodeng-planner`, `prodeng-ftm`, and `prodeng-liaison` declare
  `protect-generated` for file editing, patching, and terminal tools, plus
  `safety-rail` for terminal commands.
- `prodeng-review` declares `protect-generated` as a pre-tool hook and both
  image-observation hooks as post-tool hooks. It has no terminal tool; its
  only permitted writes are VRP records through MCP.

## Records policy

`plugins/prodeng/hooks/records-policy.json` uses schema version 1 and sets
`records_dir` to `observations/prodeng`. Stop enforcement recognizes these
artifact patterns: `**/*.prodeng.json`, `**/*.prodeng-request.json`,
`**/control-plan.csv`, `**/inspection-plan.json`, `**/sampling-plans.json`,
`**/line-balance.csv`, `**/pfmea.csv`, `**/work-instructions.md`,
`**/factory-test-spec.json`, `**/factory-test-spec.md`,
`**/prodeng-report.json`, `**/prodeng-report.md`, `**/renders/*.png`, and
`liaison/*.ux-response.json`. It ignores `examples/**`, `tests/**`, and
`.devin/**`, and allows at most two Stop denials.

The policy hint directs agents to the three `prodeng_record_*` MCP writers
or the corresponding local `record decision|impression|vision-review`
subcommands. Impressions need at least 400 characters and three sentences.
Records explain work but never affect deterministic gates.

## Canonical and repo-specific implementations

`scripts/check_shared_hooks.py` checks normalized AST hashes for the shared
`ensure_llm_profiles.py`, `_provenance.py`, `safety_rail.py`, `_records.py`,
and `require_records.py` implementations. It requires all of those files
except `_provenance.py`. Shared copies must remain canonical and be updated
together with that checker. In this plugin,
`prodeng_doctor.py`, `intake_attachments.py`, `protect_generated.py`,
`record_image_observation.py`, `record_vision_tool_event.py`, and
`report_prodeng_status.py` are prodeng-specific.
