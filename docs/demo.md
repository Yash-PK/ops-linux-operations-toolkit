# Demonstration and interview walkthrough

Run `make demo` from a clean checkout after bootstrap. The Bash driver asserts
expected outcomes for synthetic healthy, degraded and missing-tool inputs, then
checks an invalid threshold and returns to healthy input. It also inspects live
filesystem metadata and numeric identity on the current machine.

No fault is injected into the host. The fault/recovery part is a deterministic
fixture exercise, explicitly labelled `source=fixture`. Live checks have
`source=live`. On Linux, `make integration` additionally tests real OS sources.
See the validation report for the environments actually exercised.

Points to explain while reading the code:

- `backend.py`: why a narrow OS boundary permits malformed-input and missing-tool
  tests without privileged machines; why that is not Linux integration evidence.
- `collectors.py`: why MemAvailable matters, how two CPU samples differ from load,
  and why reserved blocks affect disk capacity for an ordinary user.
- `model.py`: why source unavailability must not be interpreted as healthy, and
  why the JSON preserves degraded results when the aggregate exit is 3.
- `cli.py`: explicit paths/units and validation prevent hidden scope expansion;
  JSON reports allow callers to build alerting without scraping terminal prose.
- `scripts/security.py`: `.gitignore` does not remove a secret already committed;
  outgoing history and staged blobs need independent inspection.

Production improvements would include cgroup limits, multi-sample policy,
stable machine identity, protected report transport and alert deduplication.
These are design discussion topics, not claimed delivered capabilities.
