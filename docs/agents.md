# Agents

The plugin defines four agents in `plugins/prodeng/agents/`. Each agent that
declares hooks does so explicitly because hook configuration does not
propagate to delegated agents. All four use a `prodeng` MCP configuration
that resolves `plugins/prodeng/scripts/prodeng_launcher.py` and invokes the
MCP server through the Docker-only launcher.

| Agent | Purpose and model profile | Tools | Limits and hooks | Records duties |
| --- | --- | --- | --- | --- |
| `prodeng-planner` | Authors the production plan, delegates UX requests, iterates gates, derives sibling requests. `vibebb-author`. | `terminal`, `file_editor`, `grep`, `glob`, `VisionInspectTool`, `task_tracker`, `task_tool_set`; `prodeng` MCP. | May author the contract, but generated `out/` files and request JSON are protected. Pre-tool hooks: `protect-generated` on file/patch/terminal operations; `safety-rail` on terminal. | Records non-trivial production decisions, an impression after every workflow stage, and one vision review per inspected image. |
| `prodeng-ftm` | Designs guarded factory-test-mode entry, lockout, protocol, provisioning, and exit; derives firmware/circuit requests. `vibebb-author`. | `terminal`, `file_editor`, `grep`, `glob`, `VisionInspectTool`, `task_tracker`, `task_tool_set`; `prodeng` MCP. | Works on the contract's FTM section and generated requests; does not edit sibling designs. Same `protect-generated` and `safety-rail` pre-tool hooks as the planner. | Records FTM decisions and the common stage impressions and image reviews. |
| `prodeng-liaison` | Imports supported sister artifacts, derives requests, answers UX-creator requests, and reconciles replies. `vibebb-author`. | `terminal`, `file_editor`, `grep`, `glob`, `VisionInspectTool`, `task_tracker`, `task_tool_set`; `prodeng` MCP. | Exchanges workspace JSON and delegates with `task_tool_set`; never imports sister Python packages or edits sister-owned artifacts. Same `protect-generated` and `safety-rail` pre-tool hooks. | Records request risk and response decisions, stage impressions, and image reviews when it inspects images. |
| `prodeng-review` | Provides advisory DFM/DFA/DFT findings on sister artifacts and projections. `vibebb-review`. | `file_editor`, `grep`, `glob`, `VisionInspectTool`, `ThinkTool`; `prodeng` MCP. | Read-only for source and generated files; no terminal or task-delegation tool. It never issues or overrides a verdict. `protect-generated` is a pre-tool hook; `record-vision-tool-event` runs after `inspect_image_with_vision`; `record-image-observation` runs after matching view/render/author tools. Its only writes are VRP records through MCP. | Records non-trivial review decisions, stage impressions, and a vision review for every image viewed. |

All roles must use deterministic gate results as the sole pass/fail/unknown
authority. A failed or unknown gate remains so until its inputs are corrected
and gates are rerun. Record duties and the full stage list are defined in
[Workflow](workflow.md) and [Records and vision](records-and-vision.md).
