---
description: Reconcile production-engineering requests and sibling responses.
allowed-tools:
  - terminal
---

Run `python3 "$PRODENG_PLUGIN_ROOT/scripts/prodeng_launcher.py" liaison
<directory>`. Report open, answered, mismatched, orphaned, or malformed
responses without treating reconciliation as a gate verdict.
