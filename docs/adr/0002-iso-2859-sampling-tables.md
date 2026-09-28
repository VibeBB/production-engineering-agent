# ADR-0002: ISO 2859 sampling tables

- Status: Accepted
- Decision date: 2026-09-28

## Context

Production inspection plans need consistent lot-size code letters and
single-sampling acceptance numbers. A locally approximated lookup can
disagree with the approved sampling standard.

## Decision

Implement the authored normal single-sampling table in
`src/prodeng/sampling.py`, following ISO 2859-1 Table 1 and Table 2-A for
the supported AQLs/inspection levels. Resolve arrows within the selected
AQL column and use full inspection when the prescribed sample size is at
least the lot size. The contract accepts only supported preferred AQLs and
inspection levels.

## Consequences

Sample size, acceptance number, rejection number, code letter, and full
inspection state are deterministic. Do not approximate, interpolate
unsupported AQLs, or silently substitute a different inspection level.
Applicable customer agreements and product rules still determine which
approved AQL and level may be used.
