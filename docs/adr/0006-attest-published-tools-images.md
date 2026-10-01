## SBOM attestations

The publisher generates an SPDX-2.3 SBOM for the digest-pinned tools image,
attests it with predicate type `https://spdx.dev/Document/v2.3`, and uploads
the artifact for 30 days. The lock stores the returned `sbom_attestation`
URL; locked-image checks verify it when present and warn when absent.
## Launcher-side verification

`PRODENG_VERIFY_ATTESTATION` accepts `auto` (the default), `require`, or
`off`. Before pulling a lock-provided image, and on every `prewarm`, the
launcher uses `gh attestation verify` with the lock entry and publisher
workflow. `auto` prints one note and skips for an image override, missing
attestation, missing `gh`, or failed `gh auth status`; once verification
starts, failure or timeout prevents the pull. `require` makes skip conditions
errors, while `off` never verifies. Ordinary invocations do not re-verify a
locally present image, and `--warn` doctor paths never verify.
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
