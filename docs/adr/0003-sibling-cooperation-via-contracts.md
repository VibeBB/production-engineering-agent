# ADR-0003: Sibling cooperation via workspace contracts

- Status: Accepted
- Decision date: 2026-09-28

## Context

Sibling engineering agents have independent releases and schemas. Direct
imports would couple versions and make production decisions dependent on
another agent's runtime.

## Decision

Exchange JSON artifacts through the shared workspace. Inbound adapters
normalize source fields and record system, kind, relative path, SHA-256,
and extracted facts. Outbound change requests use a versioned schema and
name a target sibling; sibling responses are reconciled informationally.
Agent-to-agent work is delegated with `task`. Do not import sibling
packages or edit sibling-owned source files.

## Consequences

Each exchange is auditable and independently versionable. Stale inbound
files fail freshness checks; unanswered, mismatched, orphan, and malformed
responses remain visible. Requests are proposals, not automatic design
edits or gate overrides.
