---
name: prodeng-contract-rules
description: Path-scoped validation rules for authored production-engineering contract files.
version: 0.1.0
license: BSD-3-Clause
paths:
  - "**/*.prodeng.json"
---

# Rules for `*.prodeng.json`

Treat the matched JSON file as the only editable source of production
engineering truth. Follow `prodeng-contract` for the full field schema and
`prodeng-workflow` for CLI use.

- Preserve `schema_version: 1` and `system: "prodeng"`; unknown properties
  are rejected.
- Keep IDs unique in each collection and preserve the required ID prefixes.
- Resolve every inspection, operation, failure-mode control, command, and
  characteristic-source reference. An `import:<system>` source requires a
  matching import entry.
- Variable characteristics need a unit and at least one of `lsl`/`usl`;
  reject limits where `lsl > usl` or the nominal lies outside the limits.
  Attribute characteristics require an acceptance criterion.
- `ftm_commands` requires an FTM object. FTM command coverage IDs and
  inspection command references must resolve.
- Use `null` for an unknown cycle time rather than estimating silently;
  the resulting takt/FTM station-fit checks remain unknown.
- Critical safety/regulatory characteristics require full inspection.
  Every PFMEA severity >= 9 control must include a full inspection.
- Never edit generated `out/**` projections or request files by hand. Run
  the `author` and `requests` CLI commands to regenerate. In the plugin,
  use the `prodeng_author` and `prodeng_requests` MCP tools; the MCP server
  uses the installed Docker-only launcher. Do not use the host package as a
  fallback.
- On validation failure, stop and correct the input. On an unknown gate,
  obtain evidence rather than turning unknown into pass.
