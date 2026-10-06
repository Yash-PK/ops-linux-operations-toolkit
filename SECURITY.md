# Security policy and operating boundary

This lab tool is not a host hardening agent. Run it as an ordinary user with
trusted system executables. No sudo is needed. Do not run it against untrusted
network mounts or publish raw local reports without review.

Never commit credentials, `.env` files, private keys, kubeconfigs, Terraform
state, sensitive logs, backup archives or customer data. Fixtures are synthetic.
Explicit certificate paths must contain public certificates, never private keys.
File freshness does not establish backup integrity or a successful restore.

The CLI validates paths/options, executes fixed argument vectors without a
shell, uses subprocess timeouts, and suppresses external stderr and sensitive
inventory fields. Timeouts do not bound kernel filesystem stalls. Size checks
reject oversized file reads and incrementally cap subprocess stdout. External
binaries are still trusted system tools, not a sandbox for arbitrary executables.

Developer tools are downloaded from verified official release URLs and SHA-256
checked. Pip accepts only hash-locked wheels. Bootstrap changes only `.venv` and
`.tools`. Checksums prove artifact identity, not the absence of malicious upstream
code. Dependency/advisory verification and its limitations are recorded in
`docs/dependencies.md`.

CI uses read-only repository permissions, no secrets, no elevated PR contexts,
and no self-hosted runner. No container/package publication or cloud deployment
is enabled. Secrets scanning covers working files, staged blobs and full outgoing
history; pattern scanning does not guarantee every secret will be detected.

For a potential vulnerability, use GitHub's private vulnerability reporting if
the repository offers it. Otherwise contact the maintainer through their public
profile without including exploit data or secrets; do not open a public issue
containing credentials. Security feature availability is not assumed enabled.
