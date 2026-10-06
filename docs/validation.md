# Validation report

Local core and clean-clone gates passed on 2026-10-06. Linux integration and
GitHub CI are pending; no release or full Linux integration designation yet.

Tested source revision: `55f15eaacf3842fa15f44751d5f21a5094bd089c`.

| Profile | Environment | Actual result | Evidence |
| --- | --- | --- | --- |
| Local | macOS Darwin 25.6.0, ARM64, Python 3.14.7, Bash 3.2.57 | 58 tests; Ruff, ShellCheck, shfmt, actionlint, links; portable live demo; working/index/full-history Gitleaks all passed | [Command report](../evidence/55f15eaacf38-local.json) |
| Clean clone | Fresh external temporary clone, independent locked bootstrap on same Mac | bootstrap, doctor, validate, demo, security all exit 0; tree clean; scratch removed | [Clone report](../evidence/55f15eaacf38-clean-clone.json) |
| Live Linux | Not run locally: development host is macOS | Unverified; configured CI profile requires real Linux sources | Pending |
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
