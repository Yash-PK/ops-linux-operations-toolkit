# Validation report

Status: implementation in progress; no release designation yet.

Required gates: locked bootstrap, Ruff, ShellCheck, shfmt, actionlint, repository
checks, fixture/unit tests, portable live demo, secret scans of staged files and
full history, and a clean temporary clone running the documented commands.
Linux integration runs separately on Linux. Hosted CI must be verified against
the exact remote commit before a versioned release.

The `evidence/` directory will contain JSON reports created by
`python3 scripts/record_validation.py --profile local` (or `linux`). The recorder
requires a clean committed source tree and records its exact revision, platform,
versions, commands, output and exit codes. Later evidence/documentation commits
do not change the identity of the originally tested code.

Optional real-systemd VM, privileged diagnostics, cgroup policy and additional
distributions remain unverified. Cloud deployment and package publication are
disabled. No host configuration is changed by the validation workflow.
