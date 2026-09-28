# prodeng OpenHands plugin

The plugin runs deterministic production-engineering CLI operations through
`scripts/prodeng_launcher.py`. Agents, commands, skills, hooks, and the MCP
server steer or invoke the core; the contract and gates remain authoritative.

Install this plugin from the repository's `plugins/prodeng/` directory in
OpenHands. The launcher requires Docker and a published, digest-locked
`ghcr.io/vibebb/prodeng-tools` image. Until the publish workflow writes a
real image lock, it fails closed with
`prodeng tools image not yet published/locked`; it never runs the CLI on
the host. Do not add placeholder lock files.

The main agent is `prodeng-planner`; specialist agents are
`prodeng-ftm`, `prodeng-liaison`, and read-only `prodeng-review`. Use
`prodeng-workflow` for the end-to-end process and the other skills for
contract, inspection, FTM, work-instruction, DFx, and liaison details.

From a checkout, diagnose plugin/package readiness with:

```bash
python3 plugins/prodeng/scripts/prodeng_launcher.py doctor --warn
```

`--warn` is session-start-only behavior and returns successfully with a
warning if the lock or image is not ready. Interactive CLI commands remain
blocked until the image can be resolved and run.
