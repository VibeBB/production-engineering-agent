---
description: Generate and inspect the factory-test-mode contract projection.
allowed-tools:
  - terminal
---

Run `python3 "$PRODENG_PLUGIN_ROOT/scripts/prodeng_launcher.py" export
<contract> [--out <directory>]` to generate the deterministic
`factory-test-spec.json` and `factory-test-spec.md`. Review entry guards,
field lockout, protocol, command timeouts, total budget, provisioning,
exit/power-cycle, and debug-port lockout against
`prodeng-factory-test-mode`. This command does not edit sibling firmware or
circuit designs; derive proposals with
`python3 "$PRODENG_PLUGIN_ROOT/scripts/prodeng_launcher.py" requests
<contract>`.
