---
name: prodeng-liaison
description: Exchange versioned JSON requests and responses with sibling agents and reconcile them without changing gate verdicts.
version: 0.1.0
license: BSD-3-Clause
triggers:
  - sibling request
  - change request
  - liaison
  - reconcile response
---

# Sibling cooperation

Cooperation uses workspace JSON and `task` delegation only. Do not import
sibling Python packages or directly edit their owned artifacts.
Inside the plugin, use the installed launcher for CLI work; do not bypass
the locked-image boundary by running the host package.

## Inbound artifacts

`import <contract> --from <kind> <file>` accepts
`circuit-brief`, `circuit-connectivity`, `mech-envelope`, `wire-contract`,
and `ux-contract`. The importer stores a normalized system/kind, source
path, SHA-256, and extracted facts; reimporting the same `(system, path)`
replaces that record. `imports.fresh` checks the file relative to the
contract directory. Missing files are unknown; changed digests fail.

## Outbound format and risk

Each `<stem>.prodeng-request.json` has this shape:

```json
{
  "schema_version": 1,
  "system": "prodeng",
  "target_agent": "firmware",
  "topic": "factory-test-mode",
  "risk": "high",
  "rationale": "The station requires guarded FTM entry and lockout.",
  "cites": ["CH-01", "R003", "IN-03"],
  "requested_changes": ["..."]
}
```

Targets are `circuit`, `firmware`, `mech`, `wire`, `ux`, `document`, and
`bard`. Each request has one or more requested changes. A high-risk request
must cite at least one declared characteristic (`CH-##`), requirement
(`R<n>`), or inspection (`IN-##`); do not cite IDs absent from the contract.

Each `<stem>.prodeng-response.json` uses this shape:

```json
{
  "schema_version": 1,
  "system": "prodeng",
  "request": "<stem>.prodeng-request.json",
  "responder": "firmware",
  "status": "accepted",
  "reason": "",
  "artifacts": []
}
```

The response status is `accepted`, `rejected`, `deferred`, or `needs_info`.
The responder must be one of the supported sibling targets.

The core derives requests deterministically:

1. Declared FTM produces a high-risk firmware `factory-test-mode` request
   for entry, lockout, interface, each command, provisioning, exit, and
   duration budget.
2. FTM interface/command nets, a failing test-access gate, or a GPIO-strap entry
   produces a high-risk circuit `test-access` request.
3. Operations with fixtures produce a low-risk mechanical `fixtures` request.
4. Harness operations produce a low-risk wire `harness-test` request covering
   continuity/hipot testability.
5. Every contract produces a low-risk document `work-instructions` request
   for controlled job instructions/control-plan documents.

## Response reconciliation

Sibling responses are `<stem>.prodeng-response.json`. Run
`liaison <directory>` to report:

- `open`: a request has no corresponding sibling response.
- `answered`: the response responder matches the request target (its
  accepted/rejected/deferred/needs-info status remains visible).
- `mismatched`: a response request reference matches a request stem but its
  responder differs from the target agent.
- `orphans`: response references have no matching request stem.
- `malformed`: request or response files cannot be parsed or violate their
  schema.

Reconciliation is informational, not a gate. Keep missing and mismatched
responses visible and request clarification from the owning sibling.
