---
name: prodeng-liaison
description: Answer UX-creator requests and reconcile versioned sibling responses without changing gate verdicts.
version: 0.1.0
license: BSD-3-Clause
triggers:
  - sibling request
  - UX-creator request
  - inbound UX request
  - change request
  - liaison
  - reconcile response
---

# Sibling cooperation

Cooperation uses workspace JSON and `task_tool_set` delegation only. Do
not import sibling Python packages or directly edit their owned artifacts.
Inside the plugin, use its `prodeng_*` MCP tools, served by the installed
Docker-only launcher; do not bypass that boundary by running the host
package.

## Inbound artifacts

`import <contract> --from <kind> <file>` accepts
`circuit-brief`, `circuit-connectivity`, `mech-envelope`, `wire-contract`,
`ux-contract`, `fpga-production`, and `firmware-production`. The importer stores a normalized system/kind, source
path, SHA-256, and extracted facts; reimporting the same `(system, path)`
replaces that record. `imports.fresh` checks the file relative to the
contract directory. Missing files are unknown; changed digests fail.
After importing `<design>.fpga-production.json`, list its device in the
programming operation's `programs`; `fpga.programming` then re-checks the
gated bitstream (flash target, SHA-256, size) at every gate run.
Do the same with `<name>.fw-production.json` and the MCU reference;
`firmware.programming` re-checks the gated ELF and that firmware was gated
against the current `factory-test-spec.json`. When the factory test mode
changes, ask firmware to re-pin its `ftm.sha256` and re-gate.

## Outbound SLP v2 format and risk

Each `<stem>.prodeng-request.json` has this shape:

```json
{
  "schema_version": 2,
  "system": "prodeng",
  "target_agent": "firmware",
  "topic": "factory-test-mode",
  "risk": "high",
  "rationale": "The station requires guarded FTM entry and lockout.",
  "cites": ["CH-01", "R003", "IN-03"],
  "requested_changes": ["..."],
  "inputs": [
    {"path": "smart-kettle.prodeng.json", "sha256": "<64 lowercase hex>"},
    {"path": "upstream/circuit-brief.json", "sha256": "<recorded import sha256>"}
  ]
}
```

Targets are `circuit`, `firmware`, `fpga`, `mech`, `wire`, `ux`, `doc`,
`dashboard`, `sim`, and `bard`. Each request binds the contract file and every
recorded imported artifact by SHA-256. A high-risk request must cite at least
one declared characteristic (`CH-##`), requirement (`R<n>`), or inspection
(`IN-##`); do not cite IDs absent from the contract.

Each `<stem>.prodeng-response.json` uses this shape:

```json
{
  "schema_version": 2,
  "system": "prodeng",
  "request": "<stem>.prodeng-request.json",
  "responder": "firmware",
  "status": "accepted",
  "reason": "",
  "artifacts": [
    {"path": "out/factory-test-spec.json", "sha256": "<64 lowercase hex>"}
  ],
  "input_hashes": {
    "smart-kettle.prodeng.json": "<request input sha256>",
    "upstream/circuit-brief.json": "<request input sha256>"
  },
  "decision_refs": ["<64-hex prodeng decision event id>"]
}
```

The response status is `accepted`, `rejected`, `deferred`, or `needs_info`.
Each artifact is SHA-bound; `input_hashes` must match the request's input
bindings for the response to remain current. `decision_refs` name the
prodeng decision records supporting the response.

The core derives requests deterministically:

1. Declared FTM produces a high-risk firmware `factory-test-mode` request
   for entry, lockout, interface, each command, provisioning, exit, and
   duration budget.
2. FTM interface/command nets, a failing test-access gate, or a GPIO-strap entry
   produces a high-risk circuit `test-access` request.
3. Operations with fixtures produce a low-risk mechanical `fixtures` request.
4. Harness operations produce a low-risk wire `harness-test` request covering
   continuity/hipot testability.
5. Every contract produces a low-risk `doc` `work-instructions` request
   for controlled job instructions/control-plan documents.

## Inbound UX-creator SLP v2

At session start, call `prodeng_ux_inbox`. It validates
`liaison/*.ux-request.json`, ignores valid requests for other targets, and
reports malformed files plus counts for `new`, `stale`, `answered`, and
`blocked`. A request is stale when an input is missing/changed or a valid
prodeng response binds different current hashes. Dependencies are blocked
until each has a valid `done` response.

Answer every `new` or `stale` request with `prodeng_ux_respond`. Use
`accepted` or `in_progress` as soon as work is acknowledged. After doing the
work, use `done` only with at least one workspace artifact, all-pass gate
verdicts, and real decision and impression references. If gates fail or are
unknown, answer `needs_info` or `rejected` with a substantive reason and
questions for the user. A dependency-blocked request may be acknowledged
with `needs_info`, `deferred`, or `rejected`; complete the work only after
the dependencies reach `done`.

Inbound requests use `schema_version: 2`, `system: "ux-creator"`, a
filename-matching `id`, `target_agent`, `stage`, `risk`, `purpose`,
`rationale`, `requested_changes`, SHA-bound `inputs`, deliverables,
acceptance criteria, optional `depends_on`, and an aware `created_at`.
For high-risk requests, ensure the rationale cites a job ID declared by a
bound UX contract input.
Responses record the responder/status/reason, current `input_hashes`,
SHA-bound artifacts, gate verdicts, decision/impression event IDs,
questions, and an aware `responded_at`. Use `prodeng_ux_respond`; do not
write response JSON by hand.

## Response reconciliation

Sibling responses are `<stem>.prodeng-response.json`. Run
`liaison <directory>` to report:

- `open`: a request has no corresponding sibling response.
- `answered`: the response responder matches the request target (its
  accepted/rejected/deferred/needs-info status remains visible).
- `mismatched`: a response request reference matches a request stem but its
  responder differs from the target agent.
- `stale`: response input hashes differ from the request's current bindings.
- `orphans`: response references have no matching request stem.
- `malformed`: request or response files cannot be parsed or violate their
  schema.

Reconciliation is informational, not a gate. Keep missing, mismatched, and
stale responses visible and request clarification from the owning sibling.
