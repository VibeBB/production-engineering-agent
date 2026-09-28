# Security policy

Report suspected vulnerabilities privately to the repository maintainers
through the security contact configured for VibeBB. Do not include exploit
instructions, credentials, customer data, or sensitive product artifacts in
a public issue.

The plugin runs its Python CLI in a locked Docker tools image and does not
fall back to host execution. Do not commit image lock placeholders or
secrets. Contracts and observations should contain only information
authorized for the workspace.

Factory-test-mode guidance is not a substitute for product security review.
Require guarded entry, production lockout, bounded commands, write-once
provisioning, clean exit, and closed debug access. Product-specific safety,
certification, and security limits must be approved by the responsible
engineering and certification owners.
