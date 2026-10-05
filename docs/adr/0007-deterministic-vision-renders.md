# ADR-0007: Deterministic vision renders

- Status: Accepted
- Decision date: 2026-10-05

## Context

Production projections are primarily text and CSV. Shop-floor review benefits
from stable, legible sheets that vision-capable agents can inspect without
changing the authored contract or gate results.

## Decision

Use Pillow as a runtime dependency to render contract-derived production
sheets as deterministic PNGs. Keep PNG generation separate from the default
authoring path; include source hashes and image hashes in a generated index,
and attach images inline only through MCP render/author tools.

## Consequences

The host and locked prodeng tools image need Pillow. Rendered files are
advisory views of deterministic projections, not independent sources of truth.
The bundled fallback font may display unsupported non-Latin glyphs as boxes;
`PRODENG_RENDER_FONT` allows a workspace to select a suitable font.
