# Commands

## OpenHands plugin commands

The following command files exist under `plugins/prodeng/commands/`; there
are no plugin slash commands for every CLI or MCP operation.

| Command | Argument hint | Behavior |
| --- | --- | --- |
| `/prodeng:doctor` | none | Calls `prodeng_doctor` and reports package, Python, and tools-image diagnostics. |
| `/prodeng:export <contract> [--out DIR]` | Contract path and optional output directory. | Calls `prodeng_export`; reads the contract and writes deterministic projections. The default is the contract's `out/<product>/` directory. |
| `/prodeng:ftm <contract>` | Contract path. | Delegates FTM design to `prodeng-ftm`, reviews the generated FTM specification, and derives proposals for firmware/circuit owners. |
| `/prodeng:gates <contract>` | Contract path. | Calls `prodeng_gates` and reports pass, fail, and unknown checks without replacing the deterministic verdict with model judgment. |
| `/prodeng:liaison <directory>` | Request/response directory. | Handles the UX-creator inbox first, then reconciles outbound prodeng requests and sibling responses. Reports open, answered, mismatched, stale, orphaned, and malformed entries as liaison state, not a gate verdict. |
| `/prodeng:plan <contract>` | Contract path. | Delegates authoring to `prodeng-planner`, inspects `prodeng_author` gates/report, and reports output and request paths. |

## CLI

The local development CLI is `python -m prodeng`; the OpenHands plugin
routes MCP execution through the Docker-only launcher. Unless noted,
successful commands return exit code `0`, input or validation errors return
`2`, and gate-bearing `author`/`gates` commands return `1` for fail or
unknown. Argparse usage errors also return `2`.

| Subcommand | Arguments | Output and exit behavior |
| --- | --- | --- |
| `doctor` | none | Environment diagnostics; returns `0`. |
| `validate CONTRACT` | Contract path. | Validates the contract and cross-references; `0` valid, `2` invalid. |
| `gates CONTRACT [--json]` | Contract path; optional machine-readable output. | Gate report; `0` pass, `1` fail/unknown, `2` invalid input. |
| `export CONTRACT [--out DIR]` | Contract and optional output directory. | Writes projections; default `CONTRACT_DIR/out/<product>/`; `0` on success, `2` on error. |
| `author CONTRACT [--out DIR] [--render]` | Contract, optional output directory, optional PNG generation. | Writes projections, sibling requests, and report. CLI rendering is opt-in; `0` pass, `1` fail/unknown, `2` on error. |
| `render CONTRACT [--out DIR]` | Contract and optional output directory. | Renders directly from the contract, without exporting projections; default `CONTRACT_DIR/out/<product>/`; `0` on success, `2` on error. |
| `import CONTRACT --from KIND FILE` | `KIND` is `circuit-brief`, `circuit-connectivity`, `mech-envelope`, `wire-contract`, `ux-contract`, or `fpga-production`. | Imports supported data into the contract and records source provenance; `0` success, `2` error. |
| `requests CONTRACT [--out DIR]` | Contract and optional request directory. | Derives and writes `*.prodeng-request.json`; default is the contract directory; `0` success, `2` error. |
| `liaison DIRECTORY` | Directory containing `*.prodeng-request.json` and `*.prodeng-response.json`. | Prints reconciliation state; `0` success, `2` error. |
| `ux inbox` | none | Scans workspace `liaison/*.ux-request.json`; `0` for a passing inbox result, `2` on error. |
| `ux respond --json FILE` | JSON object matching `UxRespondInput`. | Validates and writes a UX SLP v2 response; `0` success, `2` error. |
| `sample --lot N --aql AQL [--level LEVEL]` | Positive lot size, supported AQL, optional level (default `II`). | Prints attribute sampling plan; `0` success, `2` invalid arguments. |
| `record decision --json FILE` | JSON object matching `DecisionInput`. | Appends a decision VRP record; `0` success, `2` error. |
| `record impression --json FILE` | JSON object matching `StageImpressionInput`. | Appends a stage-impression record; `0` success, `2` error. |
| `record vision-review --json FILE` | JSON object matching `VisionReviewInput`. | Appends a vision-review record; `0` success, `2` error. |
| `record status` | none | Prints record counts and last Stop-hook status; returns `0`. |
| `mcp_server` | none | Runs the stdio MCP server until the host ends the session. |

`--version` prints the package version. CLI errors are JSON objects with
`verdict: fail`, `stage`, and `detail`. The MCP `prodeng_author` tool differs
from the CLI: its `render` option defaults to `true`; see [MCP](mcp.md).
