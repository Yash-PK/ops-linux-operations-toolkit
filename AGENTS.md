# Continuation and boundaries

This is original lab/reference engineering work. Read `docs/acceptance.md`,
`docs/validation.md`, and the sibling hub's PROJECT_STATUS.md before continuing.
Only this project may be active until its bounded core gates pass.

Architecture: Python standard-library collectors and policy evaluation in
`src/ops_toolkit`; Bash only launches repeatable demonstrations. Collectors are
read-only. Never run sudo, collect environment variables or command lines, alter
services, probe remote TLS endpoints by default, or capture network packets.
Explicit input paths may be inspected for metadata, never recursively searched.

Commands: `make help`, `make doctor`, `make bootstrap`, `make lint`, `make test`,
`make validate`, `make demo`, `make integration`, `make security`, `make clean`.
Keep fixture tests distinct from live Linux tests. Missing tools are UNKNOWN,
never PASS. CLI exit codes: 0 OK, 1 degraded, 2 invalid input, 3 unavailable.
Required gates include lint, tests, doc links, staged/history secret scanning,
and a clean-clone run. Record exact tested revision and execution environment.

Use existing Git identity. No force pushes, host configuration changes, cloud
resources, package publishing, or repository replacement. Remote creation needs
an explicitly resolved owner and passing local publishing gate. Pin dependencies
and action SHAs only after official-source verification. Save unresolved work in
`docs/validation.md` and the hub's NEXT_STEPS.md before stopping.
