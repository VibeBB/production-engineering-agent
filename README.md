# Production Engineering Agent

`prodeng` is the deterministic production-engineering core and OpenHands
plugin for turning approved product requirements and sibling design
artifacts into a manufacturing plan: control plan, inspection and sampling
plans, line balance against takt, PFMEA, work instructions, factory-test-mode
specification, and structured requests to sibling agents.

## Core invariants

- `*.prodeng.json` is the source of truth; generated `out/<product>/`
  artifacts and `*.prodeng-request.json` files are projections.
- Deterministic gates alone produce pass/fail/unknown verdicts. Unknown
  fails closed; LLM and vision output is advisory and cannot override gates.
- Sibling cooperation uses workspace JSON with SHA-256 provenance and
  `task` delegation, never sibling-package imports.
- Production safety limits and test conditions must come from the applicable
  standard and product certification procedure; the agent does not invent
  them.
- Plugin execution uses the Docker tools image boundary only. Until an
  image digest lock is published, the launcher reports
  `prodeng tools image not yet published/locked` and does not fall back to
  host execution.

## Quick start

```bash
uv sync --all-groups
uv run python -m prodeng doctor
uv run python -m prodeng author examples/smart-kettle/smart-kettle.prodeng.json
uv run python -m prodeng requests examples/smart-kettle/smart-kettle.prodeng.json
```

The package requires Python 3.12 or newer. See
[docs/README.md](docs/README.md) for architecture, operation, decisions, and
production-engineering references. Plugin assets live under
[`plugins/prodeng/`](plugins/prodeng/README.md).

## Development checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q
uv run python scripts/verify_all.py --stage fast
uv run python scripts/verify_docs.py
uv run --group sdk-check python scripts/check_plugin_load.py
```

## License

BSD-3-Clause; see [LICENSE](LICENSE).
