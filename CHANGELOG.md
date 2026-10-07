# Changelog

## 0.1.0 — 2026-10-07

- Implemented read-only health collection with typed JSON/text reports and
  explicit health, input-error and source-unavailability exit codes.
- Added synthetic source replay, threshold configuration, bounded subprocess
  deadlines, metadata inspection and safe demonstration orchestration.
- Added executable local/CI gates, locked developer tools, runbooks and
  revision-linked evidence. See validation report for actual execution status.

The core has passed local/clean-clone gates and real Linux CI, including
systemd/journal/ACL metadata on the hosted runner. See the validation report for
exact tested revisions. Versioned publication is gated on exact-revision CI. Optional VM lifecycle
profiles remain unverified; this is a lab/reference release.
