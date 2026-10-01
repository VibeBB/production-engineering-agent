# ADR-0006: Attest published tools images

Status: Accepted

## Context

The production-engineering tools image is published to GHCR and consumed from
the root image lock and the plugin's mirrored image pin. A digest identifies
image content but does not by itself record which workflow built and published
that content.

## Decision

The publish workflow creates a GitHub artifact attestation for the tools image
and stores the returned attestation URL in both lock entries. The
locked-image check verifies pinned images with this repository's publish
workflow as the signer. Existing pins without attestation metadata emit a
warning and continue; a failed verification fails the check.

## Consequences

Published image provenance is checked before the locked smoke run. The
publish job needs `id-token: write` and `attestations: write`, while the
verification job needs `attestations: read`.
