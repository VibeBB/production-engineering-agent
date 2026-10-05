# Development

## Setup and focused verification

The repository uses `uv`, Ruff, Pyright, pytest, and OpenHands SDK plugin
validation. Set up the locked environment with:

```bash
uv sync --locked --all-groups
```

Run the narrowest relevant test while iterating. The final suite used for
this repository is:

```bash
uv run python scripts/verify_docs.py
uv run ruff check .
uv run ruff format --check .
uv run pyright
env -u BASH_ENV -u "BASH_FUNC_gh%%" uv run pytest
uv run python scripts/check_shared_hooks.py
uv run --group sdk-check python scripts/check_plugin_load.py
```

The `BASH_ENV` and exported `gh`-function workaround ensures test processes
use the intended executable lookup instead of inheriting shell startup
functions. The Pyright configuration covers `src`, scripts, tests, and
plugin scripts. Pytest configuration enforces the configured coverage
threshold.

## Guards and documentation

- `scripts/verify_docs.py` checks Markdown links, required documentation
  pages, and the required ADR index entries. Keep English prose in `docs/`;
  the translated section is only in the root README.
- Tests pin workflow, launcher, hook, tool, and agent literals. Before
  changing a script/workflow/launcher or a declaration guarded by tests,
  search `tests/` for the literal and update the guard in the same commit.
  Do not weaken guard assertions to obtain a pass.
- `scripts/check_plugin_load.py` validates plugin assets against the
  installed OpenHands SDK. Run it with `--group sdk-check`.
- `scripts/check_shared_hooks.py` verifies canonical shared-hook contents
  using normalized AST hashes. The shared files are byte-preserved copies;
  a shared change must be coordinated across the family, with expected
  hashes updated intentionally.

## Examples and generated files

Contracts are edited as source; `out/`, example request/response files, and
render indexes are generated. When intentionally changing the smart-kettle
golden outputs, regenerate with the CLI rather than hand-editing:

```bash
uv run python -m prodeng author examples/smart-kettle/smart-kettle.prodeng.json
uv run python -m prodeng requests examples/smart-kettle/smart-kettle.prodeng.json
```

Review all generated diffs and ensure unrequested files did not change.
Render checks can target a disposable output directory:

```bash
uv run python -m prodeng render \
  examples/smart-kettle/smart-kettle.prodeng.json \
  --out /tmp/prodeng-renders
```

Deterministic outputs use stable ordering, UTF-8, a final newline, and no
generated timestamps. Tests compare render bytes, PNG hashes, projection
goldens, MCP image responses, and protected-file behavior.
