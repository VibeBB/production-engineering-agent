---
description: Generate deterministic control-plan, inspection, line-balance, PFMEA, work-instruction, and FTM projections.
argument-hint: <contract> [--out DIR]
allowed-tools:
  - terminal
---

Call the `prodeng_export` MCP tool with `contract_path` and, optionally,
`out_dir`. Omit `out_dir` to use the contract's `out/<product>/` directory.
Inspect generated files read-only; regenerate them from the contract rather
than editing them.
