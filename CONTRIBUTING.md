# Contributing

Read AGENTS.md and the bounded acceptance checklist first. Keep changes small,
read-only by default and supported by negative cases. Do not add a tool merely
to expand the skills list. Verify official versions, release notes and advisories
before updating dependency locks; preserve third-party attribution.

Run `make bootstrap`, `make validate`, `make demo`, and `make security`.
Run `make integration` on Linux and label unavailable integrations explicitly.
Use synthetic fixtures, never copies of live logs or credentials. Stage the
intended files and repeat security scanning before committing with your real
Git identity. Do not rewrite other contributors' history.

Record code revision, environment, commands, exit codes and assertions. A later
documentation/evidence commit is not the revision originally tested. Update
the changelog, coverage records and runbook when behavior changes. Review
threshold and exit-code compatibility as part of the CLI contract.
