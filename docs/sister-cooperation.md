# Sister cooperation

Prodeng communicates through workspace JSON files and SHA-256 provenance.
It does not import sibling Python packages or directly edit sibling-owned
files. Requests are proposals for the sibling owner, not automatic design
changes.

## Supported imports

| Sister artifact | Import kind | Imported data |
| --- | --- | --- |
| Circuit design | `circuit-brief` | Part references, net names, and connector references. |
| Circuit connectivity | `circuit-connectivity` | Net references and connector references used by test-access checks. |
| Mechanical design | `mech-envelope` | Named mechanical anchors. |
| Wire design | `wire-contract` | Wire IDs and connector IDs. |
| UX design | `ux-contract` | Product surface IDs. |

Each import records the workspace-relative source path and SHA-256 in the
contract. `imports.fresh` fails when a source changes and is unknown if its
source is missing. Intake photos are materialized by the attachment hook
for review; they are not contract import kinds.

## Outbound requests and inbound sibling replies

`prodeng_author` and `prodeng_requests` generate
`*.prodeng-request.json` schema-v2 proposals. Authoring places requests
beside the contract; `prodeng_requests` defaults there and accepts an
explicit output directory. Every request binds the contract and its
imported artifacts by path and SHA-256. The current derivation rules are:

| Target | Topic | Derivation |
| --- | --- | --- |
| `firmware` | `factory-test-mode` | An FTM is present. |
| `circuit` | `test-access` | FTM nets or measurements, a failed access check, or GPIO-strap entry calls for circuit-side test access. |
| `mech` | `fixtures` | One or more contract operations declare fixtures. |
| `wire` | `harness-test` | One or more operations have kind `harness`. |
| `doc` | `work-instructions` | Always derived for controlled instructions and inspection/control-plan typesetting. |

The schema also recognizes `fpga`, `ux`, `dashboard`, `sim`, and `bard` as
target names, but no automatic request derivation currently emits those
targets. Prodeng reads sibling `*.prodeng-response.json` v2 files and
reports their status and hash freshness with `prodeng_liaison`; a stale,
malformed, mismatched, or missing reply is not a gate verdict.

## UX-creator SLP v2

Prodeng accepts `liaison/<id>.ux-request.json` files when they validate as
strict SLP v2, target `prodeng`, and use an ID matching the filename stem.
An inbox entry reports stage, risk, purpose, dependencies, state, and detail.
Input hash changes or changed prodeng-response input hashes take precedence
and yield `stale`. Otherwise a valid prodeng response is `answered`; a
request whose dependencies lack valid `done` responses is `blocked`; the
remaining request is `new`. Malformed files are listed separately. The
inbox verdict itself is informational and returns pass.

The liaison agent answers every new or stale request with
`prodeng_ux_respond`. It can acknowledge accepted/in-progress work, complete
it, or use needs-info/deferred/rejected with a substantive reason. A `done`
reply requires at least one existing artifact, at least one gate verdict
with no fail/unknown results, and event IDs for real decision and impression
records.
When a contract path is supplied, prodeng runs the deterministic gates and
rejects caller-supplied gate results that disagree.

High-risk request rationale must cite a recognized UX job ID and declared
job source. The current accepted text patterns are intentionally limited;
their cross-check heuristics remain an improvement item. See
[Contracts](contracts.md) for the schemas and [Commands](commands.md) for
CLI entry points.
