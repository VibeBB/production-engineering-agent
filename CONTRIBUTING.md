# Contributing

Contributions should preserve the authoritative contract and deterministic
gate rules in `src/prodeng/` and `/home/ubuntu/prodeng-spec/PLAN.md`.
Do not change a gate threshold or turn an unknown into pass without an
explicit design decision and corresponding documentation.

## Development setup

Use Python 3.12+ and the repository-pinned uv version:

```bash
uv sync --all-groups
```

Before submitting, run Ruff, Pyright, pytest, docs verification, and the
plugin loader check listed in `README.md`. If editing dependency or image
pins, update the dependency checker/deferrals and operations documentation.
Do not fabricate image digests; publication workflows create locks.

## Change quality

- Add regression tests for behavior changes; preserve golden generated
  outputs by regenerating through `python -m prodeng author` and
  `python -m prodeng requests`.
- Keep imports and sibling adapters based on JSON contracts, not sibling
  package dependencies.
- Keep generated artifacts deterministic and do not hand-edit `out/**` or
  request projections.
- Treat product safety/certification limits as controlled external inputs.
- Keep code, docs, issues, PRs, and commits in English; Japanese is used in
  the `## 日本語` section of `README.md` and bilingual examples in agent/skill frontmatter.

## Review and submission

Open a focused pull request with a summary and a reproducible test plan.
Include gate-verdict evidence for contract changes, note source revisions
for safety limits, and explain any unknown or deferred check. Never include
credentials, customer-confidential files, or generated virtual environments.
