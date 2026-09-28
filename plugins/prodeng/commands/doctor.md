---
description: Diagnose the production-engineering package and locked tools-image environment.
allowed-tools:
  - terminal
---

Call the `prodeng_doctor` MCP tool and report the package, Python, and
tools-image diagnostics. If the tools image is not published and locked,
report that blocker; never execute on the host.
