---
name: prodeng-workflow
description: Run the deterministic production-engineering workflow from requirement intake through gates, projections, and sibling requests.
version: 0.1.0
license: BSD-3-Clause
triggers:
  - production engineering
  - manufacturing plan
  - production readiness
  - control plan
  - prodeng
---

# Production-engineering workflow

The `*.prodeng.json` contract is the single source of truth. `out/<product>/`
and `*.prodeng-request.json` are deterministic projections; regenerate them
through the CLI and never hand-edit them. Gate verdicts come only from the
deterministic core. An `unknown` is not a pass. LLM and vision output is L2
advisory and may identify questions or requests, but cannot alter a gate.

## End-to-end loop

1. Gather requirements, resolved assumptions, open questions, annual demand,
   working days, shifts, available time, lot size, and approved safety limits.
   Compute takt from the contract volume fields.
2. Import sibling circuit, mechanical, wire, and UX artifacts with
   `prodeng import`; each import records the path and SHA-256 provenance.
3. Author and validate the contract. Resolve load-time validation errors
   before running gates.
4. Run `prodeng author`. For every failed or unknown gate, identify its
   authoritative input, request missing evidence from its owner, update the
   contract from verified information, and rerun. Never suppress a check or
   relax its threshold to obtain pass.
5. After a passing author run, derive requests with `prodeng requests`.
   Send each request to the responsible sibling through workspace JSON and
   `task`; do not directly modify sibling-owned design files.
6. Reconcile responses with `prodeng liaison`. Unanswered or mismatched
   responses remain informationally open and do not override gates.
7. Report the gate verdict, unresolved questions, stale imports, emitted
   requests, and generated projection paths.

## CLI reference

Invoke commands as `python -m prodeng <command>` inside the locked tools
image (the plugin launcher provides this boundary):

| Command | Purpose |
| --- | --- |
| `doctor [--warn]` | Report Python, Pydantic, package, and runtime diagnostics. |
| `validate <contract>` | Parse the contract and perform load-time validation. |
| `gates <contract> [--json]` | Run deterministic checks without exporting files. |
| `export <contract> [--out DIR]` | Write projections; default is `out/<product>/` beside the contract. |
| `author <contract> [--out DIR]` | Validate, run gates, export, and write the report. |
| `import <contract> --from KIND <file>` | Import a sibling artifact and rewrite the contract with provenance. |
| `requests <contract> [--out DIR]` | Derive deterministic sibling request JSON. |
| `liaison <directory>` | Reconcile request/response files in a directory. |
| `sample --lot N --aql X [--level II]` | Resolve the ISO 2859-1 single-sampling plan. |
| `mcp_server` | Start the stdio MCP server exposing deterministic CLI operations. |

Exit codes: `0` means command success (and a passing author verdict),
`1` means a gate verdict is fail/unknown or a runtime check failed, and `2`
means invalid input or usage. A valid contract can still receive an unknown
gate verdict; report it as blocked.
