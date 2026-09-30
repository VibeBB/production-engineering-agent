# prodeng tools image

`prodeng-tools.Dockerfile` builds the Python-only CLI/MCP runtime. It follows
the Python sibling pins: uv `0.12.21` and Debian `13-slim`, with the Debian
OCI index pinned to the registry digest
`sha256:a99cfc517144bc59b1978475ec53b46ecabec7e43635402ee5b77cc54cd1b20a`.
The digest was read from the OCI registry with
`docker buildx imagetools inspect debian:13-slim`; do not replace it with a
guessed digest. The uv binary is copied from its version-pinned upstream
image. The runtime installs only core Python dependencies, not SDK-check or
development groups, and includes Git for diagnostics.

The image is published as `ghcr.io/vibebb/prodeng-tools` by
`.github/workflows/publish-prodeng-images.yml`. Its real digest is recorded
in `docker/image-digests.json` by that workflow after publication. No lock
file is checked in until the first image has actually been published; never
create a placeholder image tag or digest.

For local image construction, use a local development tag and pass it
explicitly as `PRODENG_TOOLS_IMAGE` to the launcher or locked-image runner.
The launcher itself never builds an image or falls back to host execution.
