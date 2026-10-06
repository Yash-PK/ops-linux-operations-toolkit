#!/usr/bin/env python3
"""Real Linux observations plus disposable certificate/backup failure recovery."""

import json
import os
import platform
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin/ops-toolkit"


def call(arguments, expected):
    result = subprocess.run(
        [str(CLI), *arguments, "--format", "json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    report = json.loads(result.stdout)
    if result.returncode not in expected or report["exit_code"] != result.returncode:
        raise AssertionError(f"Unexpected integration outcome: {report}")
    if report["source"] != "live":
        raise AssertionError("Integration must use live collectors")
    return report


def main():
    if platform.system() != "Linux":
        raise SystemExit("UNAVAILABLE: integration requires real Linux; no fixtures substituted")
    report = call(
        [
            "health",
            "--checks",
            "cpu,load,memory,disk,inodes,processes,sockets",
            "--disk-path",
            str(ROOT),
        ],
        {0, 1},
    )
    assert len(report["checks"]) == 7
    assert all(check["status"] in {"OK", "WARN"} for check in report["checks"])
    metrics = {check["name"]: check["metrics"] for check in report["checks"]}
    assert 0 <= metrics["cpu"]["busy_pct"] <= 100
    assert metrics["memory"]["total_bytes"] > 0
    assert 0 <= metrics["memory"]["available_bytes"] <= metrics["memory"]["total_bytes"]
    assert metrics["load"]["logical_cpus"] >= 1
    assert metrics["processes"]["count"] > 0
    assert metrics["processes"]["count"] == sum(metrics["processes"]["states"].values())
    assert metrics["sockets"]["tcp"] >= 0 and metrics["sockets"]["udp"] >= 0
    print("PASS: seven live Linux health sources and metric invariants (pressure may be WARN)")
    report = call(
        ["inspect", "--sections", "paths,identity,packages,tools", "--path", "README.md"], {0}
    )
    assert len(report["checks"]) == 4
    metrics = {check["name"]: check["metrics"] for check in report["checks"]}
    assert metrics["path"]["uid"] == (ROOT / "README.md").stat().st_uid
    assert metrics["identity"]["uid"] == os.getuid()
    assert metrics["packages"]["installed_count"] > 0
    print("PASS: live path, numeric identity, package and capability inventory")
    if not shutil.which("openssl"):
        raise SystemExit("Required Linux integration tool unavailable: openssl")
    with tempfile.TemporaryDirectory(prefix="ops-integration-") as folder:
        path = Path(folder)
        marker = path / "backup-complete.marker"
        marker.write_text("synthetic completed backup marker; no source data\n")
        call(["health", "--checks", "backup", "--backup", str(marker)], {0})
        old = time.time() - 48 * 3600
        os.utime(marker, (old, old))
        call(["health", "--checks", "backup", "--backup", str(marker)], {1})
        os.utime(marker, None)
        call(["health", "--checks", "backup", "--backup", str(marker)], {0})
        print("PASS: real temporary-file freshness healthy -> stale -> recovered")
        certificate = path / "public.crt"
        key = path / "ephemeral.key"
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-keyout",
                str(key),
                "-out",
                str(certificate),
                "-days",
                "2",
                "-subj",
                "/CN=ops-lab.invalid",
            ],
            check=True,
            timeout=30,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        call(["health", "--checks", "certificate", "--certificate", str(certificate)], {1})
        call(
            [
                "health",
                "--checks",
                "certificate",
                "--certificate",
                str(certificate),
                "--threshold",
                "certificate_days=1",
            ],
            {0},
        )
        print("PASS: real local certificate expiry with two explicit policies; key never logged")
    if Path("/run/systemd/system").exists():
        service = call(["health", "--checks", "services", "--service", "dbus.service"], {0, 1})
        assert service["checks"][0]["metrics"]["LoadState"] == "loaded"
        call(["inspect", "--sections", "journal,schedules"], {0})
        print("PASS: live systemd unit, journal and schedule metadata; no reboot behavior claimed")
    else:
        print("UNVERIFIED optional: live systemd/journal/timers (no systemd runtime)")
    if shutil.which("getfacl"):
        call(["inspect", "--sections", "paths", "--path", "README.md", "--acl"], {0})
        print("PASS: live ACL metadata")
    else:
        print("UNVERIFIED optional: live getfacl (tool absent)")
    print(
        "PASS: disposable data and ephemeral key cleaned; no services or host configuration changed"
    )


if __name__ == "__main__":
    main()
