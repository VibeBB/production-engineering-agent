---
description: Reconcile production-engineering requests and sibling responses.
argument-hint: <directory>
allowed-tools:
  - task_tracker
  - task_tool_set
  - terminal
---

Delegate sibling exchange and reconciliation to `prodeng-liaison`. Have it
call the `prodeng_liaison` MCP tool with `directory`; report open,
answered, mismatched, orphaned, or malformed responses without treating
reconciliation as a gate verdict.
