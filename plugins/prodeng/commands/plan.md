---
description: Author a production-engineering plan, run its gates, and derive sibling requests.
argument-hint: <contract>
allowed-tools:
  - task_tracker
  - task_tool_set
  - terminal
  - file_editor
---

Delegate the production plan to `prodeng-planner`. Have it call
`prodeng_author` with `contract_path`, inspect the deterministic verdict and
checks, and call `prodeng_requests` with the same path only after a pass.
Return the report path, verdict, failed or unknown checks, and request
paths. Never edit files under `out/` or generated request JSON.
