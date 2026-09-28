---
description: Generate deterministic control-plan, inspection, line-balance, PFMEA, work-instruction, and FTM projections.
allowed-tools:
  - terminal
---

Run `python3 "$PRODENG_PLUGIN_ROOT/scripts/prodeng_launcher.py" export
<contract> [--out <directory>]`. Omit `--out` to use the contract's
`out/<product>/` directory. Inspect generated files read-only; regenerate
them from the contract rather than editing them.
