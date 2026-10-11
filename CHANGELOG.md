# Changelog

## Unreleased

### Added

- `ebom_sources`, `ebom.complete` gate and `ebom.json` export: one product
  unit's engineering BOM merged from the hash-pinned circuit brief, mech
  brief and wire contract; a missing source is `unknown`, a changed or
  malformed one fails.
- `wire.continuity` gate, `wire-continuity` import kind and
  `Characteristic.continuity`: the hash-pinned wire continuity table must be
  held by a 100% continuity/isolation inspection on a harness or test
  operation; an incomplete table is `unknown`.
- SLP v2 responses carry `records_heads`, the chain head of every intact
  VRP log at answer time; UX-creator checks it on receipt. `done` is
  refused while any VRP log fails integrity.
- `packaging.oobe` gate and `packaging.contents[]`: the carton packs the
  pinned UX contract's `oobe.in_box` items once each, by a packing
  operation, top layer first in UX unboxing order.

### Changed

- Port VRP v2 from wire-agent: hash-chained logs, grounded structured
  impressions, no-re-raise, read receipts, insight lifecycle, blind
  primary/blind/tiebreak review of production renders
  (`prodeng-blind-review`), bard song receipts, and family digest/search
  through new CLI `record` kinds and MCP tools.

### Fixed

- Add executable module entrypoints for the CLI and MCP server.

## 0.1.0 — 2026-09-28

- Add deterministic production-engineering contract, gates, sampling,
  projections, sibling imports/requests, liaison, CLI, and MCP server.
- Add the smart-kettle manufacturing-plan example and golden test coverage.
- Add the OpenHands plugin, documentation, and locked Docker tools-image
  publication/verification workflow scaffolding.
