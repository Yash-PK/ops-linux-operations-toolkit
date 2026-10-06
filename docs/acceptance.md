# Core acceptance — agreed before implementation

Scope: an unprivileged, read-only Linux operations CLI with standard-library
Python logic and Bash demonstration orchestration. macOS is a development host,
not a substitute for the Linux integration environment.

- CPU utilization sampling, load per CPU, available memory, disk capacity and
  inodes, process counts/state, named systemd service state and socket counts.
- Explicit local certificate expiry and backup file freshness checks; no network
  connections or directory traversal by default.
- Explicit path metadata (mode, UID/GID, ACL availability); current identity;
  bounded journald, package, schedule and logrotate/tool capability inspection.
- JSON schema version, readable output, configurable validated thresholds,
  subprocess timeouts, summary-only stderr logging and documented exit codes.
- Synthetic healthy, degraded, missing-tool and invalid-input fixtures plus
  timeout, parser and error-path tests. No fixture is presented as live evidence.
- Live read-only portable demo; actual Linux core integration required for Linux
  integration-tested status. Real systemd/privileged diagnostics stay unverified
  unless executed in an appropriate isolated VM.
- Lint, test, documentation/security checks and clean-clone validation; README
  commands work. Missing required checks block release designation.
- Docs, CI with least privilege and pinned actions, license, review templates,
  operational runbooks, decision record and revision-linked evidence.

Out of core: host remediation, packet captures, strace attachment, remote TLS
scanning, recursive backup discovery, installed agent/daemon, production SLA,
privileged OS integration and automatic scheduling installation.
