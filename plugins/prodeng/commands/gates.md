---
description: Run deterministic production-engineering gates for a contract.
argument-hint: <contract>
allowed-tools:
  - terminal
---

Call the `prodeng_gates` MCP tool with `contract_path`. Report each pass,
fail, and unknown check. The verdict comes only from deterministic gates;
do not replace an unknown with a model judgment.
