# ADR 0001: read-only collectors with a replayable OS boundary

Status: accepted. Date: 2026-10-06.

We need demonstrable operations logic on a macOS development host without
pretending that fixtures establish Linux compatibility or altering host policy.

Decision: use the maintained Python standard library for validation, structured
output and OS access, with Bash restricted to orchestration. Isolate input
collection behind a backend and explicitly mark fixture reports. Keep optional
tools out of the runtime dependency graph; report their absence as UNKNOWN.

Alternatives considered: parsing every signal in Bash makes typed policy and
cross-platform testing harder. A monitoring agent/daemon introduces installation,
privilege and ongoing resource costs outside the bounded use case. A psutil
dependency would improve portability but hide some Linux source semantics and
introduce native packaging; it is unnecessary for this core.

Consequences: low bootstrap cost and useful fault tests, but more explicit
parsers and narrower platform claims. We must exercise real Linux independently.
Standard-library implementation does not eliminate interpreter/OS advisories.
Counters are host-visible and not quota-aware; production scheduling, alert
delivery, fleet identity and access management remain separate projects.
