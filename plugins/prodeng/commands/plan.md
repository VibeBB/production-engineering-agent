---
description: Author a production-engineering plan, run its gates, and derive sibling requests.
allowed-tools:
  - terminal
---

For `<contract>`, run
`python3 "$PRODENG_PLUGIN_ROOT/scripts/prodeng_launcher.py" author
<contract>`. If the verdict is pass, run the same launcher with
`requests <contract>`.
Return the report path, verdict, failed or unknown checks, and request paths.
Never edit files under `out/` or generated request JSON.
