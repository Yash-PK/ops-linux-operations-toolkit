"""Synthetic inputs, error paths and a portable live boundary; no host mutation."""

import io
import json
import os
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from ops_toolkit import collectors as c
from ops_toolkit.backend import Backend, FixtureBackend, load_json
from ops_toolkit.cli import main
from ops_toolkit.model import DEFAULTS, Check, InvalidInput, Unavailable, exit_code, thresholds

FIXTURES = Path(__file__).parent / "fixtures"


class ToolkitTests(unittest.TestCase):
    def setUp(self):
        self.data = load_json(FIXTURES / "healthy.json")
        self.backend = FixtureBackend(deepcopy(self.data))

    def cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        code = main(list(args), stdout=out, stderr=err)
        return code, out.getvalue(), err.getvalue()

    def fixture_cli(self, fixture, *args):
        return self.cli("health", "--format", "json", "--fixture", str(FIXTURES / fixture), *args)

    def test_healthy_all_checks(self):
        code, output, _ = self.fixture_cli(
            "healthy.json",
            "--checks",
            ",".join(c.HEALTH_NAMES),
            "--service",
            "demo.service",
            "--certificate",
            "certificate.pem",
            "--backup",
            "backup.tar",
        )
        report = json.loads(output)
        self.assertEqual(code, 0)
        self.assertEqual(len(report["checks"]), 10)
        self.assertEqual(report["source"], "fixture")
        self.assertEqual(report["schema_version"], 1)
        self.assertTrue(all(check["status"] == "OK" for check in report["checks"]))

    def test_degraded_checks_exit_one(self):
        code, output, _ = self.fixture_cli(
            "degraded.json",
            "--checks",
            ",".join(c.HEALTH_NAMES),
            "--service",
            "demo.service",
            "--certificate",
            "certificate.pem",
            "--backup",
            "backup.tar",
        )
        report = json.loads(output)
        self.assertEqual(code, 1)
        self.assertEqual(sum(check["status"] == "WARN" for check in report["checks"]), 8)

    def test_missing_tools_unknown(self):
        code, output, _ = self.fixture_cli("unavailable.json", "--checks", "sockets")
        self.assertEqual(code, 3)
        self.assertEqual(json.loads(output)["checks"][0]["status"], "UNKNOWN")

    def test_invalid_config_exit_two(self):
        code, output, _ = self.fixture_cli(
            "healthy.json", "--config", str(FIXTURES / "invalid-config.json")
        )
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output)["error"], "invalid input")

    def test_invalid_cli_values(self):
        cases = [
            ("--checks", "unknown"),
            ("--checks", "cpu,cpu"),
            ("--timeout", "nan"),
            ("--timeout", "0"),
            ("--interval", "inf"),
            ("--interval", "10"),
            ("--threshold", "cpu_pct=101"),
            ("--threshold", "cpu_pct=-1"),
            ("--threshold", "oops=3"),
            ("--threshold", "cpu_pct=nan"),
            ("--threshold", "not-an-assignment"),
            ("--checks", "services"),
            ("--checks", "backup"),
            ("--checks", "certificate"),
            ("--service", "--bad.service"),
            ("--service", "ssh"),
            ("--service", "foo;bad.service"),
            ("--service", "x" * 248 + ".service"),
            ("--disk-path", "bad\npath"),
        ]
        for case in cases:
            with self.subTest(case=case):
                # argparse rejects leading-option values before collection.
                if case == ("--service", "--bad.service"):
                    with (
                        patch("sys.stderr", io.StringIO()),
                        self.assertRaises(SystemExit) as caught,
                    ):
                        self.fixture_cli("healthy.json", *case)
                    self.assertEqual(caught.exception.code, 2)
                else:
                    self.assertEqual(self.fixture_cli("healthy.json", *case)[0], 2)

    def test_threshold_override_is_applied(self):
        code, output, _ = self.fixture_cli(
            "healthy.json", "--checks", "cpu", "--threshold", "cpu_pct=5"
        )
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output)["checks"][0]["metrics"]["warning_threshold"], 5)

    def test_threshold_validation_rejects_boolean_and_unknown(self):
        for invalid in (
            {"other": 1},
            {"thresholds": []},
            {"thresholds": {"cpu_pct": True}},
            {"thresholds": {"unknown": 2}},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(InvalidInput):
                thresholds(invalid)

    def test_unknown_precedes_degraded(self):
        self.assertEqual(exit_code([Check("a", "WARN", ""), Check("b", "UNKNOWN", "")]), 3)

    def test_cpu_delta_excludes_idle(self):
        result = c.cpu(self.backend, DEFAULTS)
        self.assertEqual(result.metrics["busy_pct"], 10)

    def test_cpu_guest_time_not_double_counted(self):
        self.backend.data["files"]["/proc/stat"] = [
            "cpu 10 0 10 80 0 0 0 0 999 999",
            "cpu 15 0 15 170 0 0 0 0 9999 9999",
        ]
        self.assertEqual(c.cpu(self.backend, DEFAULTS).metrics["busy_pct"], 10)

    def test_cpu_stalled_or_reset_is_unknown(self):
        for values in (
            ["cpu 1 0 0 9 0 0 0 0"] * 2,
            ["cpu 10 0 0 90 0 0 0 0", "cpu 1 0 0 9 0 0 0 0"],
        ):
            backend = FixtureBackend(deepcopy(self.data))
            backend.data["files"]["/proc/stat"] = values
            self.assertEqual(
                c.guarded("cpu", lambda backend=backend: c.cpu(backend, DEFAULTS)).status, "UNKNOWN"
            )

    def test_malformed_cpu_load_memory(self):
        for name, path, value in (
            ("cpu", "/proc/stat", "no aggregate line"),
            ("load", "/proc/loadavg", "nan 1 1"),
            ("load", "/proc/loadavg", "1"),
            ("memory", "/proc/meminfo", "MemTotal: 4 MB\nMemAvailable: 3 MB"),
            ("memory", "/proc/meminfo", "MemTotal: 4 kB\nMemAvailable: 5 kB"),
        ):
            backend = FixtureBackend(deepcopy(self.data))
            backend.data["files"][path] = value
            with self.subTest(name=name, value=value):
                self.assertEqual(
                    c.guarded(
                        name, lambda name=name, backend=backend: getattr(c, name)(backend, DEFAULTS)
                    ).status,
                    "UNKNOWN",
                )

    def test_memory_uses_available_not_free(self):
        result = c.memory(self.backend, DEFAULTS)
        self.assertEqual(result.metrics["used_pct"], 30)
        self.assertEqual(result.metrics["available_bytes"], 700000 * 1024)

    def test_load_is_normalized(self):
        result = c.load(self.backend, DEFAULTS)
        self.assertEqual(result.metrics["one_minute_per_cpu"], 0.1)

    def test_reserved_disk_capacity_uses_available(self):
        result = c.filesystem(self.backend, DEFAULTS, "/")
        self.assertAlmostEqual(result.metrics["used_pct"], 31.579, places=3)

    def test_no_inode_reporting_unknown(self):
        self.backend.data["disks"]["/"]["f_files"] = 0
        self.assertEqual(
            c.guarded("inodes", lambda: c.filesystem(self.backend, DEFAULTS, "/", True)).status,
            "UNKNOWN",
        )

    def test_impossible_disk_counters_unknown(self):
        self.backend.data["disks"]["/"]["f_bavail"] = 999999
        self.assertEqual(
            c.guarded("disk", lambda: c.filesystem(self.backend, DEFAULTS, "/")).status, "UNKNOWN"
        )

    def test_process_counts_without_names(self):
        result = c.processes(self.backend, DEFAULTS)
        self.assertEqual(result.metrics["states"], {"I": 1, "R": 1, "S": 2})
        self.assertEqual(result.metrics["count"], 4)

    def test_empty_process_source_unknown(self):
        self.backend.data["process_states"] = []
        self.assertEqual(
            c.guarded("processes", lambda: c.processes(self.backend, DEFAULTS)).status, "UNKNOWN"
        )

    def test_service_missing_and_failed_distinct(self):
        key = "systemctl show demo.service --property=LoadState,ActiveState,SubState --no-pager"
        for state, expected in (
            ("LoadState=not-found\nActiveState=inactive\nSubState=dead", "UNKNOWN"),
            ("LoadState=loaded\nActiveState=failed\nSubState=failed", "WARN"),
        ):
            self.backend.data["commands"][key]["stdout"] = state
            self.assertEqual(c.service(self.backend, "demo.service").status, expected)

    def test_sockets_suppress_addresses(self):
        result = c.sockets(self.backend)
        self.assertEqual(result.metrics["tcp"], 1)
        self.assertNotIn("127.0.0.1", json.dumps(result.to_dict()))

    def test_bad_socket_output_unknown(self):
        for value in (
            "unexpected output",
            "tcp LISTEN 0 0 127.0.0.1:1",
            "tcp ESTAB 0 0 local peer",
            "udp UNCONN bad 0 local peer",
        ):
            self.backend.data["commands"]["ss -H -lntu"]["stdout"] = value
            self.assertEqual(
                c.guarded("sockets", lambda: c.sockets(self.backend)).status, "UNKNOWN"
            )

    def test_bad_service_output_unknown(self):
        key = "systemctl show demo.service --property=LoadState,ActiveState,SubState --no-pager"
        for value in (
            "LoadState=loaded\nActiveState=active",
            "LoadState=loaded\nActiveState=active\nSubState=",
            "LoadState=loaded\nActiveState=active\nSubState=bad value",
        ):
            self.backend.data["commands"][key]["stdout"] = value
            self.assertEqual(
                c.guarded("service", lambda: c.service(self.backend, "demo.service")).status,
                "UNKNOWN",
            )

    def test_certificate_expired_degraded(self):
        key = "openssl x509 -in certificate.pem -noout -enddate"
        self.backend.data["commands"][key]["stdout"] = "notAfter=Jan  1 00:00:00 2025 GMT"
        result = c.certificate(self.backend, DEFAULTS, "certificate.pem")
        self.assertEqual(result.status, "WARN")
        self.assertLess(result.metrics["days_remaining"], 0)

    def test_malformed_certificate_unknown(self):
        self.backend.data["commands"]["openssl x509 -in certificate.pem -noout -enddate"][
            "stdout"
        ] = "garbage"
        self.assertEqual(
            c.guarded(
                "certificate", lambda: c.certificate(self.backend, DEFAULTS, "certificate.pem")
            ).status,
            "UNKNOWN",
        )

    def test_symlink_backup_and_certificate_rejected(self):
        for name, path in (("certificate", "certificate.pem"), ("backup", "backup.tar")):
            self.backend.data["metadata"][path]["symlink"] = True
            self.assertEqual(
                c.guarded(
                    name,
                    lambda name=name, path=path: getattr(c, name)(self.backend, DEFAULTS, path),
                ).status,
                "UNKNOWN",
            )

    def test_future_backup_unknown(self):
        self.backend.data["metadata"]["backup.tar"]["mtime"] = self.backend.now().timestamp() + 1
        self.assertEqual(
            c.guarded("backup", lambda: c.backup(self.backend, DEFAULTS, "backup.tar")).status,
            "UNKNOWN",
        )

    def test_inspection_all_sections(self):
        code, output, _ = self.cli(
            "inspect",
            "--fixture",
            str(FIXTURES / "healthy.json"),
            "--format",
            "json",
            "--sections",
            ",".join(c.INSPECT_NAMES),
            "--path",
            "sample.txt",
            "--acl",
        )
        self.assertEqual(code, 0)
        report = json.loads(output)
        self.assertEqual(len(report["checks"]), 8)
        self.assertNotIn("synthetic private", output)
        packages = next(check for check in report["checks"] if check["name"] == "packages")
        self.assertEqual(packages["metrics"]["installed_count"], 2)

    def test_invalid_inspection_args(self):
        for args in (
            ("--acl",),
            ("--sections", "paths"),
            ("--sections", "identity", "--acl"),
            ("--sections", "tools,tools"),
        ):
            self.assertEqual(self.cli("inspect", *args)[0], 2)

    def test_acl_missing_unknown(self):
        self.backend.data["commands"].pop(
            "getfacl --omit-header --numeric --absolute-names -- sample.txt"
        )
        self.assertEqual(
            c.guarded("acl", lambda: c.acl(self.backend, "sample.txt")).status, "UNKNOWN"
        )

    def test_journal_priority_only(self):
        result = c.journal(self.backend)
        self.assertEqual(result.metrics["entries"], 2)
        self.assertEqual(result.metrics["priority_counts"], {"4": 1, "6": 1})

    def test_malformed_journal_record_unknown(self):
        key = "journalctl --quiet --no-pager --output=json --output-fields=PRIORITY --lines=100 --since=-1h"
        for value in ("[]", "null", "invalid json"):
            self.backend.data["commands"][key]["stdout"] = value
            self.assertEqual(
                c.guarded("journal", lambda: c.journal(self.backend)).status, "UNKNOWN"
            )

    def test_rpm_inventory(self):
        self.backend.data["tools"] = ["rpm"]
        self.backend.data["commands"]["rpm -qa --qf %{NAME}\\n"] = {
            "stdout": "package-a\npackage-b\n"
        }
        result = c.packages(self.backend)
        self.assertEqual(result.metrics["installed_count"], 2)
        self.assertEqual(result.metrics["manager"], "rpm")

    def test_unknown_tools_are_inventory_not_false_health(self):
        code, output, _ = self.cli(
            "inspect",
            "--sections",
            "tools",
            "--fixture",
            str(FIXTURES / "unavailable.json"),
            "--format",
            "json",
        )
        self.assertEqual(code, 0)
        self.assertFalse(any(json.loads(output)["checks"][0]["metrics"].values()))
        self.assertIn("capability discovery only", output)

    def test_timeout_replay_unknown(self):
        self.backend.data["commands"]["ss -H -lntu"] = {"timeout": True}
        result = c.guarded("sockets", lambda: c.sockets(self.backend))
        self.assertEqual(result.status, "UNKNOWN")
        self.assertIn("timed out", result.message)

    def test_backend_subprocess_timeout(self):
        with self.assertRaisesRegex(Unavailable, "timed out"):
            Backend(timeout=0.1).command([sys.executable, "-c", "import time; time.sleep(5)"])

    def test_backend_failure_does_not_leak_output(self):
        with self.assertRaises(Unavailable) as caught:
            Backend().command(
                [
                    sys.executable,
                    "-c",
                    "import sys; print('secret stdout'); print('secret stderr', file=sys.stderr); sys.exit(1)",
                ]
            )
        self.assertNotIn("secret", str(caught.exception))

    def test_fixture_never_uses_live_commands(self):
        with patch(
            "ops_toolkit.backend.subprocess.Popen",
            side_effect=AssertionError("live command invoked"),
        ):
            self.assertEqual(self.fixture_cli("healthy.json")[0], 0)

    def test_fixture_timezone_required(self):
        self.backend.data["now"] = "2026-01-01T00:00:00"
        with self.assertRaises(InvalidInput):
            self.backend.now()

    def test_fixture_schema_required(self):
        with self.assertRaises(InvalidInput):
            FixtureBackend({})

    def test_non_linux_unknown(self):
        self.backend.platform = "Darwin"
        self.assertEqual(c.guarded("cpu", lambda: c.cpu(self.backend, DEFAULTS)).status, "UNKNOWN")
        self.assertEqual(c.filesystem(self.backend, DEFAULTS, "/").status, "OK")

    def test_text_and_summary_logging(self):
        code, output, log = self.cli(
            "health", "--fixture", str(FIXTURES / "healthy.json"), "--checks", "cpu", "--verbose"
        )
        self.assertEqual(code, 0)
        self.assertIn("[OK] cpu", output)
        self.assertIn("source=fixture", log)
        self.assertNotIn("busy_pct", log)

    def test_invalid_json_and_oversize_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            for value in ("not json", " " * 1_048_577, '{"thresholds":{},"thresholds":{}}'):
                path.write_text(value)
                with self.assertRaises(InvalidInput):
                    load_json(path)

    def test_json_special_files_and_symlinks_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            target = base / "input.json"
            target.write_text("{}")
            link = base / "link.json"
            link.symlink_to(target)
            fifo = base / "fifo.json"
            os.mkfifo(fifo)
            for path in (link, fifo, base):
                with self.subTest(path=path.name), self.assertRaises(InvalidInput):
                    load_json(path)

    def test_config_and_fixture_control_character_paths_rejected(self):
        for option in ("--config", "--fixture"):
            self.assertEqual(self.cli("health", option, "bad\x00path")[0], 2)

    def test_portable_live_file_metadata_and_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-backup.txt"
            path.write_text("synthetic\n")
            backend = Backend()
            self.assertEqual(c.backup(backend, DEFAULTS, str(path)).status, "OK")
            meta = c.path_metadata(backend, str(path))
            self.assertEqual(meta.metrics["uid"], os.getuid())
            self.assertEqual(c.filesystem(backend, DEFAULTS, directory).name, "disk")

    def test_process_parser_handles_parentheses_without_names(self):
        backend = Backend()
        backend.platform = "Linux"
        with (
            patch(
                "ops_toolkit.backend.Path.iterdir",
                return_value=[Path("/proc/42"), Path("/proc/sys")],
            ),
            patch.object(backend, "read", return_value="42 (synthetic ) name) S 1 2 3"),
        ):
            self.assertEqual(backend.process_states(), (["S"], 0))

    def test_command_output_bounded(self):
        with self.assertRaisesRegex(Unavailable, "bounded result"):
            Backend().command([sys.executable, "-c", "print('x' * 1048577)"])

    def test_command_valid_output(self):
        self.assertEqual(
            Backend().command([sys.executable, "-c", "print('synthetic')"]), "synthetic\n"
        )

    def test_command_stdin_is_closed(self):
        self.assertEqual(
            Backend().command([sys.executable, "-c", "import sys; print(len(sys.stdin.read()))"]),
            "0\n",
        )

    def test_command_missing_tool(self):
        with self.assertRaisesRegex(Unavailable, "not installed"):
            Backend().command(["ops-toolkit-deliberately-absent"])

    def test_fixture_nested_shapes_rejected(self):
        invalid = [
            {"files": []},
            {"files": {"/proc/stat": [1]}},
            {"commands": {"ss": []}},
            {"commands": {"ss": {"stdout": []}}},
            {"commands": {"ss": {"returncode": "0"}}},
            {"metadata": {"p": {}}},
            {"disks": {"/": []}},
            {"identity": {"uid": "name"}},
            {"directories": {"/etc/cron.d": "bad"}},
            {"process_states": "RR"},
            {"cpu_count": 0},
        ]
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(InvalidInput):
                FixtureBackend({**self.data, **changes})

    def test_fixed_command_path_ignores_caller_path(self):
        with patch.dict(os.environ, {"PATH": "/synthetic-untrusted-directory"}):
            self.assertTrue(Backend().which("sh"))
            self.assertEqual(Backend().command([sys.executable, "-c", "print('safe')"]), "safe\n")


if __name__ == "__main__":
    unittest.main()
