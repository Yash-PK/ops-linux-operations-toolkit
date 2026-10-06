#!/usr/bin/env python3
"""Report non-sensitive relevant versions; missing required tools exit nonzero."""

import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    print(f"OS={platform.system()} arch={platform.machine()} Python={platform.python_version()}")
    failed = sys.version_info < (3, 11)
    commands = [
        ["git", "--version"],
        ["bash", "--version"],
        [str(ROOT / ".venv/bin/ruff"), "--version"],
        [str(ROOT / ".tools/bin/shellcheck"), "--version"],
        [str(ROOT / ".tools/bin/shfmt"), "--version"],
        [str(ROOT / ".tools/bin/actionlint"), "--version"],
        [str(ROOT / ".tools/bin/gitleaks"), "version"],
    ]
    for command in commands:
        if not shutil.which(command[0]):
            print(f"REQUIRED MISSING: {Path(command[0]).name}; run make bootstrap")
            failed = True
            continue
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        print(result.stdout.strip())
        failed |= result.returncode != 0
    if platform.system() != "Linux":
        print("Linux integration: UNAVAILABLE on this host; fixture tests are not Linux execution.")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
