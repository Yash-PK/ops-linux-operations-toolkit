#!/usr/bin/env bash
# Deterministic fixture failure/recovery plus explicit read-only portable checks.
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$repo_root"

expect_exit() {
  local expected="$1"
  shift
  local actual=0
  "$@" || actual=$?
  if [[ "$actual" -ne "$expected" ]]; then
    printf 'Expected exit %s, observed %s\n' "$expected" "$actual" >&2
    exit 1
  fi
  printf 'ASSERT expected exit=%s observed exit=%s\n' "$expected" "$actual"
}

printf '%s\n' 'FIXTURE: healthy baseline'
expect_exit 0 bin/ops-toolkit health --fixture tests/fixtures/healthy.json
printf '%s\n' 'FIXTURE: degraded -> baseline recovery (no host fault injection)'
expect_exit 1 bin/ops-toolkit health --fixture tests/fixtures/degraded.json
expect_exit 0 bin/ops-toolkit health --fixture tests/fixtures/healthy.json
printf '%s\n' 'FIXTURE: unavailable tool and invalid configuration'
expect_exit 3 bin/ops-toolkit health --fixture tests/fixtures/unavailable.json --checks sockets
expect_exit 2 bin/ops-toolkit health --fixture tests/fixtures/healthy.json --config tests/fixtures/invalid-config.json
printf '%s\n' 'LIVE: portable read-only disk and inode collection (health may be degraded)'
live_status=0
bin/ops-toolkit health --checks disk,inodes --disk-path . || live_status=$?
if [[ "$live_status" -gt 1 ]]; then
  printf 'Portable live collection unavailable: exit=%s\n' "$live_status" >&2
  exit "$live_status"
fi
printf '%s\n' 'LIVE: explicit repository metadata and numeric identity'
expect_exit 0 bin/ops-toolkit inspect --sections paths,identity,tools --path README.md
printf '%s\n' 'Demo completed. Fixture outcomes do not prove Linux/systemd integration.'
