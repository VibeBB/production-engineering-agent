# ADR-0001: Deterministic core and gates

- Status: Accepted
- Decision date: 2026-09-28

## Context

Production plans affect safety, quality, delivery, and auditability. An
LLM-only judgment cannot provide stable traceability or reproducible
acceptance. Missing evidence must not silently produce a pass.

## Decision

Keep contract parsing, cross-reference validation, sampling, gate
evaluation, projections, imports, requests, and reports in a deterministic
Python core. The authored JSON contract is truth; projections are generated
from it. Gate states are pass/fail/unknown and the verdict passes only when
all checks pass. LLM/vision observations and sibling reconciliation remain
advisory.

## Consequences

Generated artifacts are reproducible and byte-comparable. Missing inputs
remain unknown or invalid instead of being inferred. Any schema or gate
change requires a code review and tests. No plugin prompt can override the
core verdict.
