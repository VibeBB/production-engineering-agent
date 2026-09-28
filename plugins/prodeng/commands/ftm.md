---
description: Generate and inspect the factory-test-mode contract projection.
argument-hint: <contract>
allowed-tools:
  - task_tracker
  - task_tool_set
  - terminal
  - file_editor
---

Delegate FTM design to `prodeng-ftm`. Have it call `prodeng_export` with
`contract_path` to generate deterministic `factory-test-spec.json` and
`factory-test-spec.md`, then review entry guards, field lockout, protocol,
command timeouts, total budget, provisioning, exit/power-cycle, and
debug-port lockout against `prodeng-factory-test-mode`. Derive proposals
with `prodeng_requests` using the contract path. Do not edit sibling
firmware or circuit designs.
