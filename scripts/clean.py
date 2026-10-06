#!/usr/bin/env python3
"""Remove only the known repository-owned runtime directory."""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / ".runtime"
if target.is_symlink():
    raise SystemExit("Refusing symlink cleanup")
if target.is_dir():
    shutil.rmtree(target)
print(
    "Cleaned only .runtime if present. Developer tool caches retained; no host resources created."
)
