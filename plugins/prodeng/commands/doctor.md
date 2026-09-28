---
description: Diagnose the production-engineering package and locked tools-image environment.
allowed-tools:
  - terminal
---

Run `python3 "$PRODENG_PLUGIN_ROOT/scripts/prodeng_launcher.py" doctor` and
report the package, Python, and tools-image diagnostics. If the tools image
is not published and locked, report that blocker; never execute on the host.
