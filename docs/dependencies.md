# Dependency selection and verification

Reviewed on **2026-10-06**. The CLI uses Python's standard library and a small
Bash launcher; there are no third-party runtime Python packages. Development
tools run locally from ignored project directories. Bootstrap must not install
global packages or modify the host interpreter.

## Runtime

Python 3.14.7 is the exact interpreter available for the initial local work.
The [Python support table](https://devguide.python.org/versions/) lists 3.14 in
bugfix support and 3.11–3.13 in security support on the review date. Python 3.10
reached end of life on 2026-10-01 and is not a supported target for new work.
Syntax compatibility with another release is not proof that this project ran
on it; consult the validation report for exercised versions.

The [3.14.7 release changelog](https://docs.python.org/release/3.14.7/whatsnew/changelog.html#python-3-14-7-final)
was read, including security fixes for archive extraction and HTTP response
handling. Bootstrap should use a patched interpreter, bounded downloads, and
copy only an explicitly named regular archive member after verifying its hash.
It must never call unrestricted `extractall` on a downloaded archive.

Bash 3.2 is a syntax-compatibility floor for Apple's existing launcher, not a
claim that the old upstream Bash branch receives security maintenance. Use
the operating system's supported, patched Bash on Linux. The GNU Bash website
and manual could not be retrieved during this review (network timeouts), so
current upstream Bash support was not independently verified. No Bash upgrade
or host package change is performed by this project.

## Pinned development tools

| Tool | Selected release | Purpose | Official documentation/release |
| --- | --- | --- | --- |
| Ruff | 0.16.10 | Python linting and formatting | [Release](https://github.com/astral-sh/ruff/releases/tag/0.16.10), [version policy](https://docs.astral.sh/ruff/versioning/) |
| ShellCheck | 0.11.0 | Bash static analysis | [Release and changelog](https://github.com/koalaman/shellcheck/releases/tag/v0.11.0) |
| shfmt | 3.14.1 | Consistent shell formatting | [Release](https://github.com/mvdan/sh/releases/tag/v3.14.1) |
| actionlint | 1.7.12 | GitHub Actions static validation | [Release](https://github.com/rhysd/actionlint/releases/tag/v1.7.12) |
| Gitleaks | 8.30.1 | Staged-file and outgoing-history secret scanning | [Release](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1) |

These were the latest published stable releases returned by the repositories'
`releases/latest` endpoints at review time. Release notes were consulted before
selection. A hash pin freezes inputs; it does not imply indefinite support.

Ruff's [PyPI metadata](https://pypi.org/pypi/ruff/0.16.10/json) declares Python
`>=3.7`. `requirements-dev.lock` pins its version and wheel SHA-256 values;
installation must use pip's `--require-hashes` and binary wheels. Ruff changes
lint/format behavior in minor versions, so upgrades require rerunning the gates.

`tools.lock.json` contains official release URLs, exact SHA-256 digests, and
executable archive members for macOS ARM64 and Linux x86-64/ARM64. Digests came
from the official GitHub release API `assets[].digest` fields. Every one of the
12 listed assets was downloaded into memory, hashed independently, and matched
against that metadata. Each tar archive's member names were inspected; no
downloaded binary was executed as part of this dependency review. Runtime
verification on each architecture remains a separate validation result.

The release-API provenance is:

- [ShellCheck metadata](https://api.github.com/repos/koalaman/shellcheck/releases/tags/v0.11.0)
- [shfmt metadata](https://api.github.com/repos/mvdan/sh/releases/tags/v3.14.1)
- [actionlint metadata](https://api.github.com/repos/rhysd/actionlint/releases/tags/v1.7.12)
- [Gitleaks metadata](https://api.github.com/repos/gitleaks/gitleaks/releases/tags/v8.30.1)

This verifies byte consistency against the upstream release service over TLS.
It does not independently authenticate the upstream build environment or prove
the absence of vulnerabilities. The lock records optional `license_member`
paths so archive license notices can be retained with local installations.
Third-party tools retain their upstream licenses; the repository's MIT license
covers original project code, not those binaries. Do not commit tool binaries
or relicense upstream files.

## GitHub Actions pins

Each tag was resolved through the official GitHub REST API to an object of
type `commit`; the full 40-character commit is used in workflow configuration.

| Action | Release | Verified commit |
| --- | --- | --- |
| actions/checkout | [v7.0.1](https://github.com/actions/checkout/releases/tag/v7.0.1) | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| actions/setup-python | [v7.0.0](https://github.com/actions/setup-python/releases/tag/v7.0.0) | `5fda3b95a4ea91299a34e894583c3862153e4b97` |
| actions/upload-artifact | [v7.0.1](https://github.com/actions/upload-artifact/releases/tag/v7.0.1) | `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` |

For independent verification, query
`https://api.github.com/repos/OWNER/REPO/git/ref/tags/VERSION` for the listed
action. An annotated tag would require resolving the tag object; these three
were direct commit references.

The [checkout documentation](https://github.com/actions/checkout) and
[setup-python documentation](https://github.com/actions/setup-python) specify
the Node 24 runtime and a minimum Actions runner version of 2.327.1. Current
standard GitHub-hosted runners are the intended CI environment; no self-hosted
runner is configured. Checkout uses `persist-credentials: false`, and workflow
permissions default to `contents: read`. Artifact upload must name only the
sanitized validation output, never the workspace or live host inventories.

## Advisory review and uncertainty

The following official security surfaces were checked on the review date:

- [Ruff advisories API](https://api.github.com/repos/astral-sh/ruff/security-advisories)
  returned an empty published-advisory list.
- [ShellCheck security](https://github.com/koalaman/shellcheck/security),
  [shfmt security](https://github.com/mvdan/sh/security), and
  [actionlint security](https://github.com/rhysd/actionlint/security) showed no
  published advisories and no repository security policy. No long-term support
  promise was found in those surfaces.
- [Gitleaks security](https://github.com/gitleaks/gitleaks/security) states that
  only the latest version is supported; it showed no published advisories.
- [checkout advisory API](https://api.github.com/repos/actions/checkout/security-advisories)
  and [setup-python advisory API](https://api.github.com/repos/actions/setup-python/security-advisories)
  returned empty lists; [upload-artifact security](https://github.com/actions/upload-artifact/security)
  showed no published advisories.

An empty advisory list is a limited observation, not a vulnerability-free
attestation. Transitive binary components have not received a complete SBOM/CVE
audit in this milestone. Recheck upstream releases and advisories before an
upgrade, then update hashes and action commits through review and rerun local
and CI gates. Do not silently float a pin to make a failed check pass.

## Low-resource choice

Standard-library `unittest` is sufficient for deterministic fixture tests and
avoids an additional test-framework dependency graph. Ruff combines Python
linting and formatting; ShellCheck and shfmt cover distinct shell concerns;
actionlint validates workflow structure; Gitleaks scans secret patterns.
There is no container, VM, cloud, package registry publication, or privileged
daemon dependency in this milestone. Tools are independent command-line
binaries, so heavyweight profiles can remain outside the first project.
