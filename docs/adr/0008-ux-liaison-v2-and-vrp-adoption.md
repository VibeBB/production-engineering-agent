# ADR 0008: UX liaison v2 responder and VRP adoption

- Status: Accepted
- Date: 2026-10-05

## Context

Prodeng exchanges manufacturing requests with sibling plugins and must
answer UX-creator work requests without importing UX-creator code. A request
or answer must remain tied to the exact inputs that were reviewed. In
addition, a product decision, stage conclusion, and image review should
remain readable by sibling plugins and later sessions rather than existing
only in a transient agent conversation.

## Decision

Implement a strict local mirror of the UX-creator SLP v2 request and response
schemas. Prodeng scans workspace `liaison/` files, validates IDs and
SHA-256-bound inputs, detects stale requests and unfinished dependencies,
and writes responses atomically. A `done` response requires hashed
artifacts, passing gate verdicts, and references to actual decision and
impression VRP events.

Adopt the shared VibeBB Record Protocol v1 using three append-only JSONL
logs: decisions, stage impressions, and vision reviews. Use the shared
canonical record hooks for validation and Stop enforcement, and expose
typed prodeng writers through both MCP and CLI.

## Consequences

- Prodeng and UX-creator can exchange versioned workspace files without a
  runtime dependency on one another.
- File/input hashes expose stale work; response status and inbox state are
  informational, not deterministic gate verdicts.
- Record references provide durable evidence for design choices, stage
  outcomes, and image inspection; record contents never override gates.
- The strict mirrored schemas require compatibility fixtures and producer
  cross-checks as future maintenance work.
