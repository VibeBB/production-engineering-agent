# Operations

## SBOM attestations

`publish-prodeng-images.yml` generates and attests an SPDX-2.3 SBOM for the
published tools digest and uploads it for 30 days. The lock records the
returned `sbom_attestation` URL, which `locked-image-check.yml` verifies when
present; an absent URL warns and continues.

## Launcher-side verification

`PRODENG_VERIFY_ATTESTATION` accepts `auto` (the default), `require`, or
`off`. Before pulling a lock-provided image, and on every `prewarm`, the
launcher uses `gh attestation verify` with the lock entry and publisher
workflow. `auto` prints one note and skips for an image override, missing
attestation, missing `gh`, or failed `gh auth status`; once verification
starts, failure or timeout prevents the pull. `require` makes skip conditions
errors, while `off` never verifies. Ordinary invocations do not re-verify a
locally present image, and `--warn` doctor paths never verify.

## Local development

Use Python 3.12+ and uv 0.12.21:

```bash
uv sync --all-groups
uv run python -m prodeng validate examples/smart-kettle/smart-kettle.prodeng.json
uv run python -m prodeng author examples/smart-kettle/smart-kettle.prodeng.json
uv run python -m prodeng requests examples/smart-kettle/smart-kettle.prodeng.json
```

An author run validates the contract, evaluates gates, writes projections,
and emits reports. Exit `0` is success/pass, `1` is a fail/unknown verdict
or runtime failure, and `2` is invalid input/usage. `gates --json` provides
machine-readable checks. `sample --lot N --aql X --level II` resolves a
single-sampling plan.

Run verification before a change is submitted:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q
uv run python scripts/verify_all.py --stage fast
uv run python scripts/verify_docs.py
uv run --group sdk-check python scripts/check_plugin_load.py
```

Workflow changes are checked by the repository's actionlint and zizmor
workflow. The required image lock is validated before the locked smoke run;
when an attestation URL is present, the check verifies it against the publish
workflow before pulling the image. Existing locks without attestation metadata
emit a warning and remain compatible.

## Plugin and tools image

The OpenHands launcher and `scripts/run_in_locked_image.py` use Docker only.
The published image is `ghcr.io/vibebb/prodeng-tools`; its digest is
recorded by `publish-prodeng-images.yml` after publication. Do not create a
placeholder lock. Before a real lock exists, the plugin launcher prints
`prodeng tools image not yet published/locked` and refuses execution rather
than falling back to host Python. `doctor --warn` is the exception for
session startup: it reports a warning and returns zero.

Build/check the image after an authoritative digest is available:

```bash
python scripts/print_locked_image.py --entry prodeng_tools
python scripts/pull_locked_image.py --entry prodeng_tools
python scripts/run_in_locked_image.py -- python scripts/e2e_authoring.py \
  --contract examples/smart-kettle/smart-kettle.prodeng.json \
  --out examples/smart-kettle/out/smart-kettle
```

Image lock changes must be produced by the publish workflow or its
`update_image_digest_lock.py` helper using an actual registry digest. The
publish workflow creates a GitHub artifact attestation for the tools image and
records its URL in both lock entries; the locked-image workflow verifies that
provenance when available. The
base image digest and uv version belong in
`docker/prodeng-tools.Dockerfile`; CI action references remain SHA-pinned.

## Sibling interchange

Run `prodeng import <contract> --from <kind> <file>` on the actual source
artifact. The importer stores SHA-256 provenance; gate evaluation rechecks
the file relative to the contract directory. If an import is missing or
stale, reacquire/reimport the approved source rather than hand-editing the
digest.

After authoring, `prodeng requests <contract>` writes
`<stem>.prodeng-request.json`. The owning sibling supplies
`<stem>.prodeng-response.json`; use `prodeng liaison <directory>` to
reconcile. An answered response is not itself a gate pass and a missing
response remains open.

## Product safety and inspection

Critical safety/regulatory characteristics require full inspection.
Sampling plans for allowed major/minor characteristics use the approved
ISO 2859-1/JIS Z 9015-1 level and AQL. Exact mains hipot, dielectric,
ground-bond, and other certification test values come from the applicable
standard and product certification procedure, not this tool. Workmanship
criteria and rework remain controlled process/product inputs.

## Dependency updates and releases

`scripts/check_dependency_updates.py` compares direct/transitive Python
dependencies, uv, Python, pinned actions, workflow tools, and Docker base
surfaces. It performs external version queries; inspect the generated
candidate report and review upstream changelogs before updating. Deferred
updates require a rationale and review date in
`scripts/dependency_update_deferrals.json`. A failed external query is counted
as unknown in the JSON report, and the scheduled issue remains open until
unknown and outdated counts are both zero.

Release tags must match the Python package and plugin version. Build and
publish the tools image only through the locked workflow; the workflow
records the returned digest and image-tool metadata. The release workflow
publishes the package/plugin release after verification.

## Troubleshooting

- **Missing tools image lock:** do not add a fake lock or run Python on the
  host through the plugin. Wait for the publish workflow to produce the
  real image digest.
- **Docker unavailable:** CLI/plugin execution through the launcher is
  blocked. Use the local development CLI only for repository development,
  not as an OpenHands plugin fallback.
- **Unknown gate:** identify the missing source measurement, cycle time,
  circuit import, open question, or AQL plan; obtain evidence from the
  responsible owner and rerun.
- **Stale import:** reimport the original source; never edit SHA-256
  provenance manually.
- **Unsafe proposed limit:** stop and request the product certification or
  process owner’s approved value and revision.

## CI runner network auditing

CI and image-publishing jobs use `step-security/harden-runner` in audit-only mode. It observes network egress without blocking requests; per-run insights are available in the GitHub Actions job summary.

## Digest-lock PR verification

The publisher dispatches `ci.yml` and `workflow-lint.yml` on the lock branch, then polls the authoritative required-check set for up to 30 minutes. Non-required failures do not block publishing; a concluded required-check failure or a PR closed without merge fails the job. A PR merged externally triggers the existing post-merge main workflows without waiting for their results. If required checks remain pending at the deadline, the publisher arms squash auto-merge with branch deletion and exits successfully so branch protection can complete the merge.

SPDX SBOM generation prefers the GHCR registry source, writes temporary data under the runner's temporary directory, and disables file metadata. A guard reports disk space and SBOM size immediately after generation and fails above 16 MiB, the attestation service's maximum.
