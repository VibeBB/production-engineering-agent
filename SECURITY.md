# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| 0.1.x | Yes |

## Reporting a vulnerability

Please do not open public issues for security vulnerabilities. Report them
via GitHub's private vulnerability reporting on this repository, or by
contacting the maintainer directly. Include:

- the affected version/commit,
- a minimal reproduction (contract JSON, command, or payload),
- impact assessment if known.

You can expect an acknowledgement within a few days. We will coordinate a
fix and disclosure with you before publishing details. Do not include
exploit instructions, credentials, customer data, or sensitive product
artifacts in a public issue.

## Scope notes

The plugin runs its Python CLI in a locked Docker tools image and does not
fall back to host execution. Contracts and observations should contain only
information authorized for the workspace. The MCP server speaks stdio only
and never opens network listeners.

Factory-test-mode guidance is not a substitute for product security review:
require guarded entry, production lockout, bounded commands, write-once
provisioning, clean exit, and closed debug access. Product-specific safety,
certification, and security limits must be approved by the responsible
engineering and certification owners.

Secrets must never be written to logs, inputs, contracts, or commits; see
the invariants in [AGENTS.md](AGENTS.md).
