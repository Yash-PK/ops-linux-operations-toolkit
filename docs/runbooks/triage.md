# Read-only triage runbook

1. Run `make doctor` for development-tool diagnostics. Runtime commands do not
   require developer tools; run `bin/ops-toolkit --version` to identify the CLI.
2. Run `bin/ops-toolkit health --format json`. Capture the exit code immediately.
   Review individual results even when exit 3 masks a degraded check's exit 1.
3. For UNKNOWN, distinguish unsupported OS, missing tool, unreadable source,
   malformed output and command timeout. Do not run sudo automatically. An
   operator must decide whether broader read permissions are appropriate.
4. For CPU/load pressure, compare repeated samples and process state counts.
   `vmstat`, `iostat` and `sar` are advertised only as available capabilities;
   they are not invoked or claimed as implemented analysis by this toolkit.
5. For disk/inode pressure, check the explicit mount path. Do not delete files
   from a triage command. Reserved space and per-user quotas can differ from
   filesystem totals; inspect those separately under an approved procedure.
6. For an inactive service, confirm the exact unit name and use a separately
   authorized service runbook. This tool never restarts services.
7. For expiring certificates, check trust/name/renewal separately. For stale
   backup markers, investigate the backup job and perform an isolated restore;
   freshness alone is insufficient.

`lsof`, `strace` and `tcpdump` may reveal sensitive data or need privileges. This
project only inventories their availability. No attachment or packet capture is
performed. The future isolated networking lab owns bounded capture exercises.

Recovery from the synthetic demo: replay the healthy fixture. Recovery from a
host incident is outside this tool's permissions. Preserve a redacted report,
timestamp and exit code; never upload process arguments, internal addresses or
raw journal messages as portfolio evidence.
