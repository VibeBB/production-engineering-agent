# ADR-0005: TWI Job Instruction work instructions

- Status: Accepted
- Decision date: 2026-09-28

## Context

Production operators need concise, teachable process instructions linked to
quality checks, tools, ESD controls, and safety conditions. Free-form
paragraphs are difficult to audit against process steps.

## Decision

Model operation work elements as TWI Job Instruction rows: Major step,
Key points, and Reasons. Include process tools/fixtures, relevant 4M
context, ESD and safety controls, and linked inspection IDs in the
generated work-instructions projection. The document sibling owns
controlled document numbering, style, revision, translation, and release.

## Consequences

Missing work elements or key points fail deterministic work-instruction
gates. The production-engineering core provides structured content but does
not claim to release a controlled work instruction or invent process
parameters.
