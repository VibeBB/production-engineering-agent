# Repository memory

- `src/prodeng/contract.py` and the authored `*.prodeng.json` are
  authoritative; generated files under `out/` and
  `*.prodeng-request.json` are protected projections.
- Gate thresholds and schema rules follow `/home/ubuntu/prodeng-spec/PLAN.md`.
  Missing evidence remains `unknown`; do not invent certification limits.
- Sibling interchange is JSON with SHA-256 provenance; never import sibling
  packages.
- The plugin launcher is Docker-only. Until a real image lock exists, the
  expected failure is `prodeng tools image not yet published/locked`.
- The smart-kettle example is regenerated only with
  `python -m prodeng author` followed by `python -m prodeng requests`.
- Plugin check targets OpenHands SDK/tools 1.51.0; uv is pinned at 0.12.22.
