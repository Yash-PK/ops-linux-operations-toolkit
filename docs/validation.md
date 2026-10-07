# Validation report

Core local, clean-clone and live Linux CI gates passed. The supported Linux
profile is integration-tested on the standard GitHub-hosted Ubuntu x86-64 runner.
This does not establish full OS lifecycle behavior or production readiness.

Tested source revision: `55f15eaacf3842fa15f44751d5f21a5094bd089c`.

| Profile | Environment | Actual result | Evidence |
| --- | --- | --- | --- |
| Local | macOS Darwin 25.6.0, ARM64, Python 3.14.7, Bash 3.2.57 | 58 tests; Ruff, ShellCheck, shfmt, actionlint, links; portable live demo; working/index/full-history Gitleaks all passed | [Command report](../evidence/55f15eaacf38-local.json) |
| Clean clone | Fresh external temporary clone, independent locked bootstrap on same Mac | bootstrap, doctor, validate, demo, security all exit 0; tree clean; scratch removed | [Clone report](../evidence/55f15eaacf38-clean-clone.json) |
| Live Linux CI | Ubuntu 24.04 runner, kernel 6.17.0-1022-azure, x86-64, Python 3.14.7 | All gates including real Linux integration exit 0 | [Linux report](../evidence/0b0f077933bb-linux.json) |
| Real systemd VM / privileged diagnostics | Not provisioned | Unverified | None |

The fixture suite covers all ten health capabilities and inventory parsers with
healthy/degraded/missing-tool/invalid inputs, timeout/output limits, error
redaction, duplicate JSON keys, special-file rejection and policy edge cases.
The live Mac demo exercises only disk, inode and metadata/identity capabilities.

Resolved during validation: sandbox command PATH initially selected Python 3.9;
bootstrap used the verified explicit Python 3.14 path. Make now uses its local
virtual environment. Lint caught late-bound test lambdas; the test task initially
omitted its source import path. Both defects were fixed before the tested commit.
The first pre-commit security run intentionally failed the required history gate
because no history existed; after the initial commit all history scans passed.
No checks were weakened or skips represented as passing tests.

Evidence files record exact source revision, timestamps, environment, tool
versions, commands, exits and sanitized output. This report and the evidence are
committed afterward; that later documentation commit is not the tested source
revision. Required local publishing gates pass; release additionally requires
passing Linux integration and CI for the exact published revision.

No cloud resources, VMs, containers or host configuration changes were created.
Disposable test and clone directories were cleaned. Repo-local developer caches
remain ignored. Full outgoing-history Gitleaks reported no findings; this is not
a vulnerability-free guarantee. GNU Bash upstream support verification and
transitive binary SBOM/CVE analysis remain explicitly limited in dependency docs.

## Published Linux evidence

[Run 37459272607](https://github.com/Yash-PK/ops-linux-operations-toolkit/actions/runs/37459272607)
passed for `0b0f077933bb06e2b9016f50ff5d8b1fbcebddf4`. The artifact was downloaded
and inspected; the report above is a preserved copy, not generated output from
this Mac. Actual live assertions covered CPU/load/memory/disk/inodes/processes/
sockets, metadata/identity/package inventory, a temporary backup marker's
fresh-stale-recovered cycle, and a real local certificate checked with two
policies. The runner also exercised a loaded dbus systemd unit, journal metadata,
schedule counts and getfacl. Temporary data and ephemeral certificate keys were
cleaned. No service mutation, boot/reboot, remote TLS, cgroup or privileged
diagnostic behavior is claimed.

Repository owner `Yash-PK`, public visibility, default branch `main`, and remote
SHA were independently verified. Free repository-level secret scanning, push
protection and private vulnerability reporting were enabled and read back as
enabled. Branch protection is proposed in the publishing guide, not applied.

Subsequent documentation/evidence commits preserve this original revision
accounting. Their CI results must be checked separately before release.

The subsequent evidence/documentation revision
`ada345ab55a9b551ff186e05cb62970d67dae03f` also passed
[run 37571448796](https://github.com/Yash-PK/ops-linux-operations-toolkit/actions/runs/37571448796).
Source and validation scripts are unchanged from the locally clean-clone-tested
revision; differences are evidence and documentation only.
