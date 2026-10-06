"""Read-only collectors: explicit inputs, bounded output and no remediation."""

import json
import math
import re
from collections import Counter
from datetime import datetime, timezone

from .model import Check, Unavailable, threshold_check

HEALTH_NAMES = (
    "cpu",
    "load",
    "memory",
    "disk",
    "inodes",
    "processes",
    "services",
    "sockets",
    "certificate",
    "backup",
)
DEFAULT_HEALTH = HEALTH_NAMES[:6] + ("sockets",)
INSPECT_NAMES = ("paths", "identity", "journal", "schedules", "packages", "tools")
TOOLS = (
    "ss",
    "lsof",
    "vmstat",
    "iostat",
    "sar",
    "strace",
    "tcpdump",
    "getfacl",
    "systemctl",
    "journalctl",
    "logrotate",
    "cron",
    "crond",
    "dpkg-query",
    "rpm",
    "openssl",
)


def guarded(name, operation):
    try:
        return operation()
    except Unavailable as exc:
        return Check(name, "UNKNOWN", str(exc))
    except (ValueError, TypeError, KeyError, IndexError, OverflowError) as exc:
        # External data is untrusted; malformed data cannot become a pass.
        return Check(name, "UNKNOWN", f"malformed source data ({type(exc).__name__})")


def finite(value):
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError("invalid nonnegative number")
    return result


def cpu(backend, policy):
    backend.linux()

    def sample():
        line = next(
            line for line in backend.read("/proc/stat").splitlines() if line.startswith("cpu ")
        )
        values = [finite(item) for item in line.split()[1:9]]
        if len(values) != 8:
            raise ValueError("CPU fields missing")
        return sum(values), values[3] + values[4]

    try:
        before, idle_before = sample()
        backend.pause()
        after, idle_after = sample()
    except StopIteration as exc:
        raise ValueError("aggregate CPU line missing") from exc
    delta, idle_delta = after - before, idle_after - idle_before
    if delta <= 0 or idle_delta < 0 or idle_delta > delta:
        raise Unavailable("CPU counters did not advance consistently")
    return threshold_check(
        "cpu",
        100 * (delta - idle_delta) / delta,
        policy["cpu_pct"],
        "busy_pct",
        metrics={
            "sampling_seconds": backend.interval,
            "scope": "host-visible aggregate; not cgroup quota",
        },
    )


def load(backend, policy):
    backend.linux()
    values = [finite(value) for value in backend.read("/proc/loadavg").split()[:3]]
    if len(values) != 3:
        raise ValueError("load fields missing")
    cpus = backend.cpu_count()
    return threshold_check(
        "load",
        values[0] / cpus,
        policy["load_per_cpu"],
        "one_minute_per_cpu",
        metrics={
            "load_1m": values[0],
            "load_5m": values[1],
            "load_15m": values[2],
            "logical_cpus": cpus,
            "scope": "OS-visible CPUs; not cgroup quota",
        },
    )


def memory(backend, policy):
    backend.linux()
    values = {}
    for line in backend.read("/proc/meminfo").splitlines():
        fields = line.split()
        if fields and fields[0] in {"MemTotal:", "MemAvailable:"}:
            if len(fields) != 3 or fields[2] != "kB":
                raise ValueError("memory units")
            values[fields[0][:-1]] = finite(fields[1]) * 1024
    total, available = values["MemTotal"], values["MemAvailable"]
    if total <= 0 or available > total:
        raise ValueError("memory counters")
    return threshold_check(
        "memory",
        100 * (total - available) / total,
        policy["memory_pct"],
        "used_pct",
        metrics={
            "total_bytes": int(total),
            "available_bytes": int(available),
            "scope": "/proc/meminfo; not cgroup quota",
        },
    )


def filesystem(backend, policy, path, inodes=False):
    data = backend.disk(path)
    if inodes:
        total, free = finite(data["f_files"]), finite(data["f_ffree"])
        name, metric = "inodes", "used_pct"
        limit = policy["inodes_pct"]
        if total == 0:
            raise Unavailable("filesystem does not report inode capacity")
        metrics = {"path": path, "total_inodes": int(total), "free_inodes": int(free)}
        used_pct = 100 * (total - free) / total
    else:
        total, free, available = (
            finite(data["f_blocks"]),
            finite(data["f_bfree"]),
            finite(data["f_bavail"]),
        )
        if total == 0 or available > free:
            raise ValueError("filesystem counters")
        # Reserved blocks are unavailable to an ordinary user: match df semantics.
        used, usable = total - free, total - free + available
        if usable <= 0:
            raise Unavailable("filesystem has no usable capacity")
        used_pct = 100 * used / usable
        size = finite(data["f_frsize"])
        if size <= 0:
            raise ValueError("filesystem fragment size")
        name, metric, limit = "disk", "used_pct", policy["disk_pct"]
        metrics = {
            "path": path,
            "total_bytes": int(total * size),
            "available_bytes": int(available * size),
        }
    if free > total:
        raise ValueError("filesystem counters")
    return threshold_check(name, used_pct, limit, metric, metrics=metrics)


def processes(backend, policy):
    states, skipped = backend.process_states()
    if not states:
        raise Unavailable("no readable process states")
    if any(not isinstance(state, str) or len(state) != 1 for state in states):
        raise ValueError("invalid process state")
    return threshold_check(
        "processes",
        len(states),
        policy["process_count"],
        "count",
        metrics={
            "states": dict(sorted(Counter(states).items())),
            "unreadable_or_exited": skipped,
            "scope": "visible /proc entries; command lines never collected",
        },
    )


def service(backend, unit):
    backend.linux()
    raw = backend.command(
        ["systemctl", "show", unit, "--property=LoadState,ActiveState,SubState", "--no-pager"]
    )
    lines = raw.splitlines()
    if len(lines) != 3 or any("=" not in line for line in lines):
        raise ValueError("service property lines")
    values = dict(line.split("=", 1) for line in lines)
    if set(values) != {"LoadState", "ActiveState", "SubState"}:
        raise ValueError("service fields")
    if any(not re.fullmatch(r"[a-z][a-z-]{0,63}", value) for value in values.values()):
        raise ValueError("malformed service state")
    if values["LoadState"] != "loaded":
        return Check(f"service:{unit}", "UNKNOWN", "unit is not loaded", values)
    healthy = values["ActiveState"] == "active"
    return Check(
        f"service:{unit}",
        "OK" if healthy else "WARN",
        "service active" if healthy else "service not active",
        values,
    )


def sockets(backend):
    backend.linux()
    raw = backend.command(["ss", "-H", "-lntu"])
    counts = Counter()
    for line in raw.splitlines():
        fields = line.split()
        if len(fields) != 6 or fields[0] not in {"tcp", "udp"}:
            raise ValueError("socket fields")
        if fields[1] != {"tcp": "LISTEN", "udp": "UNCONN"}[fields[0]] or any(
            not value.isdecimal() for value in fields[2:4]
        ):
            raise ValueError("socket state or queue fields")
        counts[fields[0]] += 1
    return Check(
        "sockets",
        "OK",
        "listening TCP and bound UDP inventory",
        {
            "tcp": counts["tcp"],
            "udp": counts["udp"],
            "scope": "current network namespace; addresses suppressed",
        },
    )


def certificate(backend, policy, path):
    meta = backend.metadata(path)
    if not meta["regular"] or meta["symlink"]:
        raise Unavailable("certificate must be an explicit regular file, not a symlink")
    raw = backend.command(["openssl", "x509", "-in", path, "-noout", "-enddate"]).strip()
    if not raw.startswith("notAfter="):
        raise ValueError("certificate end date")
    expiry = datetime.strptime(raw[9:], "%b %d %H:%M:%S %Y GMT").replace(tzinfo=timezone.utc)
    days = (expiry - backend.now()).total_seconds() / 86400
    return threshold_check(
        "certificate",
        days,
        policy["certificate_days"],
        "days_remaining",
        below=True,
        metrics={
            "not_after": expiry.isoformat(),
            "scope": "expiry only; no chain, hostname or private-key validation",
        },
    )


def backup(backend, policy, path):
    meta = backend.metadata(path)
    if not meta["regular"] or meta["symlink"]:
        raise Unavailable("backup must be an explicit regular file, not a symlink")
    age = (backend.now().timestamp() - finite(meta["mtime"])) / 3600
    if age < 0:
        raise Unavailable("backup modification time is in the future; check clocks")
    return threshold_check(
        "backup",
        age,
        policy["backup_hours"],
        "age_hours",
        metrics={"scope": "mtime freshness only; does not prove integrity or recoverability"},
    )


def health(backend, args, policy):
    results = []
    operations = {
        "cpu": lambda: cpu(backend, policy),
        "load": lambda: load(backend, policy),
        "memory": lambda: memory(backend, policy),
        "disk": lambda: filesystem(backend, policy, args.disk_path),
        "inodes": lambda: filesystem(backend, policy, args.disk_path, True),
        "processes": lambda: processes(backend, policy),
        "sockets": lambda: sockets(backend),
        "certificate": lambda: certificate(backend, policy, args.certificate),
        "backup": lambda: backup(backend, policy, args.backup),
    }
    for name in args.checks:
        if name == "services":
            for unit in args.service:
                results.append(guarded(f"service:{unit}", lambda unit=unit: service(backend, unit)))
        else:
            results.append(guarded(name, operations[name]))
    return results


def path_metadata(backend, path):
    data = backend.metadata(path)
    metrics = {
        "path": path,
        "mode": f"{data['mode']:04o}",
        "uid": data["uid"],
        "gid": data["gid"],
        "symlink": data["symlink"],
        "world_writable": bool(data["mode"] & 0o002),
    }
    return Check("path", "OK", "metadata inspection; no permission policy inferred", metrics)


def acl(backend, path):
    backend.linux()
    raw = backend.command(["getfacl", "--omit-header", "--numeric", "--absolute-names", "--", path])
    entries = [line for line in raw.splitlines() if line and not line.startswith("#")]
    return Check(
        "acl",
        "OK",
        "ACL entry inventory; principals suppressed",
        {
            "path": path,
            "entry_count": len(entries),
            "extended": any(line.startswith(("mask:", "default:")) for line in entries),
        },
    )


def journal(backend):
    backend.linux()
    raw = backend.command(
        [
            "journalctl",
            "--quiet",
            "--no-pager",
            "--output=json",
            "--output-fields=PRIORITY",
            "--lines=100",
            "--since=-1h",
        ]
    )
    priorities = Counter()
    for line in raw.splitlines():
        record = json.loads(line)
        if not isinstance(record, dict):
            raise ValueError("journal record must be an object")
        priority = str(record.get("PRIORITY", "unknown"))
        if priority not in {str(i) for i in range(8)} | {"unknown"}:
            priority = "unknown"
        priorities[priority] += 1
    return Check(
        "journal",
        "OK",
        "bounded visible journal metadata; messages suppressed",
        {
            "entries": sum(priorities.values()),
            "priority_counts": dict(sorted(priorities.items())),
            "limit": 100,
            "since": "1 hour",
            "scope": "visible journal only; permissions may restrict coverage",
        },
    )


def timers(backend):
    backend.linux()
    raw = backend.command(["systemctl", "list-timers", "--all", "--no-legend", "--no-pager"])
    return Check(
        "timers",
        "OK",
        "system timer inventory; names suppressed",
        {"count": len([line for line in raw.splitlines() if line.strip()])},
    )


def file_schedules(backend):
    backend.linux()
    paths = (
        "/etc/cron.d",
        "/etc/cron.hourly",
        "/etc/cron.daily",
        "/etc/cron.weekly",
        "/etc/cron.monthly",
        "/etc/logrotate.d",
    )
    counts = {
        path: len([name for name in backend.entries(path) if not name.startswith(".")])
        for path in paths
    }
    return Check(
        "schedule-files",
        "OK",
        "system cron/logrotate entry counts; no contents collected",
        {
            "entry_counts": counts,
            "scope": "directory entries only; does not prove schedules execute; user crontabs excluded",
        },
    )


def packages(backend):
    backend.linux()
    if backend.which("dpkg-query"):
        manager = "dpkg-query"
        raw = backend.command(["dpkg-query", "-W", "-f=${db:Status-Status}\\n"])
        count = sum(line == "installed" for line in raw.splitlines())
    elif backend.which("rpm"):
        manager = "rpm"
        raw = backend.command(["rpm", "-qa", "--qf", "%{NAME}\\n"])
        count = sum(bool(line.strip()) for line in raw.splitlines())
    else:
        raise Unavailable("no supported package inventory tool (dpkg-query or rpm)")
    return Check(
        "packages",
        "OK",
        "installed package count; names suppressed",
        {
            "manager": manager,
            "installed_count": count,
            "scope": "inventory only; not an advisory or update check",
        },
    )


def inspect(backend, args):
    results = []
    for section in args.sections:
        if section == "paths":
            for path in args.path:
                results.append(guarded("path", lambda path=path: path_metadata(backend, path)))
                if args.acl:
                    results.append(guarded("acl", lambda path=path: acl(backend, path)))
        elif section == "identity":
            results.append(
                guarded(
                    "identity",
                    lambda: Check(
                        "identity",
                        "OK",
                        "numeric identity and local account inventory",
                        backend.identity(),
                    ),
                )
            )
        elif section == "journal":
            results.append(guarded("journal", lambda: journal(backend)))
        elif section == "schedules":
            results.append(guarded("schedule-files", lambda: file_schedules(backend)))
            results.append(guarded("timers", lambda: timers(backend)))
        elif section == "packages":
            results.append(guarded("packages", lambda: packages(backend)))
        elif section == "tools":
            results.append(
                Check(
                    "tools",
                    "OK",
                    "capability discovery only; diagnostics not executed",
                    {name: backend.which(name) for name in TOOLS},
                )
            )
    return results
