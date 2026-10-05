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
never edits files or issues verdicts; its only writes are VRP records through
the record MCP tools.

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

`verify_all.py` also accepts `--group` (lint/unit/docker), `--match`, and
`--shard K/N` to run a subset of a stage's commands so CI can spread one
stage across jobs; `--list` dumps the tagged command table.

Keep projections byte-deterministic: stable ordering, no timestamps in
generated reports, UTF-8 text, and one final newline. Use the narrowest
tests and checks for a change, then the prescribed verification set before
submitting.

The fast verification stage includes the shared-hook checker and enforces the
configured line-coverage threshold. Shared hooks are canonical across the
family; change all 9 copies together and update EXPECTED. `intake_attachments.py`,
`protect_generated.py`, `record_image_observation.py`,
`record_vision_tool_event.py`, and `report_prodeng_status.py` are
repo-specific.

All source, docs, issue/PR text, and commit messages are English, except
the `## 日本語` section of `README.md` and Japanese examples in agent/skill frontmatter. Follow the
repository's pinned Ruff/Pyright configuration and Pydantic v2 conventions.

## Git safety

Use focused commits with imperative English messages. Stage explicit paths;
never use `git add .`. Do not amend, force-push, skip hooks, push to main,
run destructive reset/clean operations, or stage secrets. Do not commit
generated build environments or image lock placeholders.

Shared workflows are canonical across the family; change all 11 copies together and update `EXPECTED` in `scripts/check_shared_workflows.py`.

## CI/CD

Digest-lock PRs use `scripts/publish_image_pin_pr.sh`: the lock PR's own
`pull_request` runs are the single CI path (dispatched runs never satisfy
required checks), so the publisher only approves the `action_required` runs
and polls the authoritative required-check set for up to 15 minutes.
Non-required failures do not block publishing; a concluded required-check
failure or a PR closed without merge fails the job. A PR merged externally
triggers the post-merge main workflows. If required checks are still
pending at the deadline, the publisher arms squash auto-merge with branch
deletion and exits successfully; the digest-lock sweep dispatches the
post-merge verification on main once the armed merge lands.

SPDX SBOM generation prefers registry pulls, uses runner temporary storage,
and disables file metadata. The attested SBOM is package-level SPDX 2.3;
file entries and relationships involving files are omitted to stay below
16 MiB. The full Syft SBOM is attached to the workflow run as a 90-day
artifact.

The release bump state machine is script-backed
(`scripts/release_bump.sh`, covered by `tests/test_release_bump.py` with
stubbed `gh`/`git`), and the publish workflow accepts a `dry_run` dispatch
input that rehearses the gate chain against a locally loaded image without
pushing, attesting, or locking.
