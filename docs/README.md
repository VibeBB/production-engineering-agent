# Documentation

## Product and workflow

- [Architecture](architecture.md): deterministic core, plugin, records, and
  gate authority.
- [Workflow](workflow.md): intake through contract, gates, projections,
  vision review, liaison, and handoff.
- [Agents](agents.md): the four agent roles, tools, models, hooks, limits,
  and record responsibilities.
- [Skills](skills.md): the eight installed prodeng skills and their scope.
- [Commands](commands.md): every `/prodeng` command and CLI subcommand,
  arguments, and exit behavior.

## Interfaces and records

- [MCP](mcp.md): tool schemas, read/write annotations, outputs, and inline
  images.
- [Hooks](hooks.md): plugin and agent hook events, enforcement, and
  canonical shared hooks.
- [Contracts](contracts.md): contract, request/response, render-index, VRP,
  and generated-output schemas.
- [Records and vision](records-and-vision.md): VRP v1, image-review
  checklists, and advisory semantics.
- [Sister cooperation](sister-cooperation.md): import, request, response,
  and UX-creator SLP v2 boundaries.

## Operations and development

- [Operations](operations.md): local development, authoring, plugin/image
  operation, release, and troubleshooting.
- [Development](development.md): verification, guard tests, golden
  regeneration, and shared-hook policy.
- [Performance and limits](performance-and-limits.md): measured smart-kettle
  timings, image sizes, payload size, and caps.
- [Improvement notes](improvement-notes.md): open follow-up work.

## Research

- [Production-engineering research note](research/production-engineering.md):
  practice areas, standards references, takt formula, and terminology.
- [SDK v1.50.0 feature evaluation](research/sdk-v1.50.0-feature-evaluation.md):
  OpenHands SDK and uv update decisions.
- [SDK v1.50.1 feature evaluation](research/sdk-v1.50.1-feature-evaluation.md):
  OpenHands SDK/tools adoption decisions.
- [SDK v1.51.0 feature evaluation](research/sdk-v1.51.0-feature-evaluation.md):
  OpenHands SDK/tools, uv, and deferral decisions.
- [SDK v1.52.0 feature evaluation](research/sdk-v1.52.0-feature-evaluation.md):
  OpenHands SDK/tools adoption decisions.

## Architecture decisions

- [0001 — Deterministic core and gates](adr/0001-deterministic-core-and-gates.md)
- [0002 — ISO 2859 sampling tables](adr/0002-iso-2859-sampling-tables.md)
- [0003 — Sibling cooperation via contracts](adr/0003-sibling-cooperation-via-contracts.md)
- [0004 — Factory-test-mode contract](adr/0004-factory-test-mode-contract.md)
- [0005 — Work instructions in TWI format](adr/0005-work-instructions-twi.md)
- [0006 — Attest published tools images](adr/0006-attest-published-tools-images.md)
- [0007 — Deterministic vision renders](adr/0007-deterministic-vision-renders.md)
- [0008 — UX liaison v2 and VRP adoption](adr/0008-ux-liaison-v2-and-vrp-adoption.md)
