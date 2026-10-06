# Architecture and trust boundaries

`bin/ops-toolkit` locates the repository from the script path and launches the
Python module without depending on the caller's working directory. Python
validates options before collection. `model.py` owns thresholds and exit-code
policy; `collectors.py` translates narrow input observations into checks;
`backend.py` is the only OS boundary. The fixture backend replays synthetic
input bytes and never executes commands.

The data pipeline is deliberately small. Linux counters come from `/proc`;
filesystem metadata comes from `statvfs`/`lstat`; service, socket, certificate
and inventory observations use argument-vector subprocess calls with deadlines.
Results are aggregated without suppressing individual unavailability. No shell
command is built from user input. Bash only provides launch/demo orchestration.

Read access is still a security boundary. Inputs are explicit paths or fixed
system files. There is no recursive backup search. There is no access to shell
history, environment dumps, credentials, process command lines or packet data.
Inventory reports intentionally omit identities and names where counts suffice.

CPU busy percentage uses two aggregate counter samples, excluding guest fields
already included in user/nice and treating idle+iowait as idle. Load is normalized
by visible logical CPUs. Memory uses MemAvailable rather than MemFree. Disk use
accounts for blocks unavailable to an ordinary user. These are triage signals,
not cgroup-aware capacity planning or a measured SLA.

Tests at the backend boundary cover parser/error behavior without requiring a
particular host. Linux integration separately exercises real sources. The
dependency lock and CI action SHAs support repeatable tooling; mutable hosted
runner images and the OS command packages are recorded environmental dependencies,
not claimed bit-for-bit reproducible components.
