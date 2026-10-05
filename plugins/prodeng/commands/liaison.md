---
description: Reconcile production-engineering requests and sibling responses.
argument-hint: <directory>
allowed-tools:
  - task_tracker
  - task_tool_set
  - terminal
---

Delegate UX liaison work to `prodeng-liaison`. First have it call
`prodeng_ux_inbox` and answer every new or stale request with
`prodeng_ux_respond`; acknowledge dependency-blocked requests when the
dependencies have valid `done` responses. Then call `prodeng_liaison` with
`directory` to reconcile outbound prodeng requests and sibling responses.
Report open, answered, mismatched, stale, orphaned, or malformed responses
without treating reconciliation as a gate verdict.
