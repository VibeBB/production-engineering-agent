# Agent Working Agreement

This repository contains the deterministic `prodeng` production-engineering
core and its OpenHands plugin. `docs/` describes architecture and operation;
`docs/adr/` records design decisions; the Pydantic contract in
`src/prodeng/contract.py` is the manufacturing-plan source of truth.

## Invariants

- The authored `*.prodeng.json` contract is truth. Files under `out/` and
  `*.prodeng-request.json` are generated projections and must be regenerated
  from the contract, never edited by hand.
- Only deterministic gates in `src/prodeng/gates.py` issue pass/fail/unknown.
  `unknown` fails closed; do not weaken thresholds to obtain pass.
- LLM and vision outputs are L2 advisory. They can identify evidence gaps
  or propose a sibling request but cannot override a gate.
- Sibling cooperation is through JSON artifacts, SHA-256 provenance, and
  OpenHands `task_tool_set` delegation. Never import sibling packages or edit their
  owned source artifacts directly.
- Safety/certification values must be traceable to an applicable standard
  and the product certification procedure. Do not invent voltages, leakage
  limits, bond resistance limits, or rework acceptance.
- Do not write secrets into contracts, logs, test fixtures, or commits.

## Layout and plugin boundary

`src/prodeng/` contains the Python 3.12+ core; `plugins/prodeng/` contains
agents, commands, skills, hooks, launcher, and MCP configuration. Every
plugin CLI/MCP action runs in the locked `ghcr.io/vibebb/prodeng-tools`
image through `plugins/prodeng/scripts/prodeng_launcher.py`. The launcher
does not fall back to host execution. Do not create placeholder
`tools-image.json` or `docker/image-digests.json`; the publish workflow
creates digest locks after an image is published.

Agents declare their hooks explicitly because hooks do not propagate to
sub-agents. Delegate with the OpenHands `task_tool_set` tool. AgentDefinitions do not
declare a `skills:` field; prompts reference skill files. The review agent
is read-only and has no MCP configuration.

## Development

```bash
uv sync --all-groups
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q
uv run python scripts/verify_all.py --stage fast
uv run python scripts/verify_docs.py
uv run --group sdk-check python scripts/check_plugin_load.py
```

Keep projections byte-deterministic: stable ordering, no timestamps in
generated reports, UTF-8 text, and one final newline. Use the narrowest
tests and checks for a change, then the prescribed verification set before
submitting.

All source, docs, issue/PR text, and commit messages are English, except
`README.ja.md` and Japanese examples in agent/skill frontmatter. Follow the
repository's pinned Ruff/Pyright configuration and Pydantic v2 conventions.

## Git safety

Use focused commits with imperative English messages. Stage explicit paths;
never use `git add .`. Do not amend, force-push, skip hooks, push to main,
run destructive reset/clean operations, or stage secrets. Do not commit
generated build environments or image lock placeholders.
