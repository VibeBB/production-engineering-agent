---
description: Run deterministic production-engineering gates for a contract.
allowed-tools:
  - terminal
---

Run `python3 "$PRODENG_PLUGIN_ROOT/scripts/prodeng_launcher.py" gates
<contract> --json`. Report each pass, fail, and unknown check. The verdict
comes only from the CLI; do not replace an unknown with a model judgment.
