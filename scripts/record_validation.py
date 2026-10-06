#!/usr/bin/env python3
"""Run documented gates and record actual revision, commands and exit codes."""

import argparse
import datetime
import json
import platform
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=["local", "linux"], default="local")
    args = parser.parse_args()
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    if dirty:
        raise SystemExit("Commit changes first: evidence must identify clean tested source")
    commands = [["make", "doctor"], ["make", "validate"], ["make", "demo"], ["make", "security"]]
    if args.profile == "linux":
        if platform.system() != "Linux":
            raise SystemExit("Linux evidence requires a Linux runtime")
        commands.append(["make", "integration"])
    report = {
        "schema_version": 1,
        "revision": revision,
        "clean_at_start": True,
        "environment": {
            "os": platform.system(),
            "release": platform.release(),
            "architecture": platform.machine(),
            "python": platform.python_version(),
        },
        "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "profile": args.profile,
        "commands": [],
    }
    for command in commands:
        start = time.monotonic()
        try:
            result = subprocess.run(
                command,
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=600,
            )
        except subprocess.TimeoutExpired as exc:
            partial = exc.stdout or b""
            if isinstance(partial, bytes):
                partial = partial.decode("utf-8", errors="replace")
            result = subprocess.CompletedProcess(
                command, 124, partial + "\nTIMEOUT after 600 seconds\n"
            )
        output = result.stdout.replace(str(ROOT), "$REPO").replace(str(Path.home()), "$HOME")
        report["commands"].append(
            {
                "argv": command,
                "exit_code": result.returncode,
                "duration_seconds": round(time.monotonic() - start, 3),
                "output": output,
            }
        )
        print(f"{' '.join(command)}: exit {result.returncode}", flush=True)
    report["finished_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    report["passed"] = all(item["exit_code"] == 0 for item in report["commands"])
    folder = ROOT / "evidence"
    folder.mkdir(exist_ok=True)
    destination = folder / f"{revision[:12]}-{args.profile}.json"
    destination.write_text(json.dumps(report, indent=2) + "\n")
    print(destination.relative_to(ROOT))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
