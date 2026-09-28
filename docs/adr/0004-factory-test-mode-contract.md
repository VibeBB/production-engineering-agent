# ADR-0004: Factory-test-mode contract

- Status: Accepted
- Decision date: 2026-09-28

## Context

Factory test requires controlled access to embedded firmware and hardware
without leaving a production escape path, unbounded station time, or
untraceable provisioning.

## Decision

Represent entry conditions, field lockout, transport/settings/nets,
commands, per-command timeouts, characteristic coverage, provisioning,
exit, and maximum duration in the contract. Require at least two entry
conditions, a non-`none` lockout, command coverage and inspection links,
and duration/station-fit gates. Distinguish firmware-owned behavior from
circuit-owned test access.

## Consequences

FTM is reviewable and projects to a stable specification and sibling
requests. An unspecified limit or missing test access is not inferred.
Product-security approval, irreversible lockout verification, and
certification-specific test criteria remain owner responsibilities.
