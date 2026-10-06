"""Exercise clean-clone failure accounting without downloads or remote writes."""

import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SPEC = importlib.util.spec_from_file_location(
    "clean_clone",
    Path(__file__).resolve().parents[1] / "scripts/clean_clone.py",
)
clean_clone = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(clean_clone)
REVISION = "a" * 40


class CleanCloneGateTests(unittest.TestCase):
    def setUp(self):
        patch = mock.patch("sys.stdout", new_callable=io.StringIO)
        patch.start()
        self.addCleanup(patch.stop)

    def test_timeout_is_failed_evidence_and_partial_output_is_redacted(self):
        error = subprocess.TimeoutExpired(["make", "validate"], 10, output=b"/private/task stalled")
        with mock.patch.object(clean_clone.subprocess, "run", side_effect=error):
            result = clean_clone.run_command(
                ["make", "validate"],
                Path("/private/task"),
                {"/private/task": "$REPO"},
                10,
            )
        self.assertEqual(result["exit_code"], 124)
        self.assertTrue(result["timed_out"])
        self.assertEqual(result["output"], "$REPO stalled")

    def test_dirty_source_rejected_before_cloning_or_network(self):
        with (
            mock.patch.object(
                clean_clone.subprocess, "check_output", side_effect=[REVISION, " M x"]
            ),
            mock.patch.object(clean_clone, "run_command") as run,
        ):
            with self.assertRaisesRegex(SystemExit, "clean source"):
                clean_clone.validate()
        run.assert_not_called()

    def test_bootstrap_timeout_writes_failed_report_and_cleans_temporary_clone(self):
        seen = []

        def fake_run(command, cwd, replacements, timeout=600):
            seen.append((command, Path(cwd)))
            is_bootstrap = command[0] == "make"
            return {
                "argv": command,
                "exit_code": 124 if is_bootstrap else 0,
                "timed_out": is_bootstrap,
                "output": REVISION + "\n" if command[:2] == ["git", "rev-parse"] else "",
            }

        with tempfile.TemporaryDirectory(prefix="ops-gate-test-") as folder:
            root = Path(folder).resolve()
            with (
                mock.patch.object(
                    clean_clone.subprocess, "check_output", side_effect=[REVISION, ""]
                ),
                mock.patch.object(clean_clone, "run_command", side_effect=fake_run),
            ):
                self.assertFalse(clean_clone.validate(root))
            report = json.loads(
                (root / "evidence" / f"{REVISION[:12]}-clean-clone.json").read_text()
            )
            self.assertFalse(report["passed"])
            self.assertEqual(report["revision"], REVISION)
            self.assertEqual(report["not_run"], ["doctor", "validate", "demo", "security"])
            self.assertTrue(report["temporary_clone_removed"])
            self.assertIn("--no-local", seen[0][0])
            scratch = Path(seen[0][0][-1])
            self.assertFalse(scratch.is_relative_to(root))
            self.assertFalse(scratch.parent.exists())
            self.assertEqual([item[0][-1] for item in seen if item[0][0] == "make"], ["bootstrap"])

    def test_different_clone_revision_blocks_all_make_targets(self):
        def fake_run(command, cwd, replacements, timeout=600):
            return {"argv": command, "exit_code": 0, "output": "different-revision"}

        with tempfile.TemporaryDirectory(prefix="ops-gate-test-") as folder:
            root = Path(folder)
            with (
                mock.patch.object(
                    clean_clone.subprocess, "check_output", side_effect=[REVISION, ""]
                ),
                mock.patch.object(clean_clone, "run_command", side_effect=fake_run) as run,
            ):
                self.assertFalse(clean_clone.validate(root))
            report = json.loads(
                (root / "evidence" / f"{REVISION[:12]}-clean-clone.json").read_text()
            )
            self.assertFalse(report["assertions"][0]["passed"])
            self.assertEqual(report["not_run"], list(clean_clone.TARGETS))
            self.assertFalse(any(call.args[0][0] == "make" for call in run.call_args_list))

    def test_success_requires_every_documented_target_without_recursive_gate(self):
        def fake_run(command, cwd, replacements, timeout=600):
            return {
                "argv": command,
                "exit_code": 0,
                "output": REVISION if command[:2] == ["git", "rev-parse"] else "",
            }

        with tempfile.TemporaryDirectory(prefix="ops-gate-test-") as folder:
            root = Path(folder)
            with (
                mock.patch.object(
                    clean_clone.subprocess, "check_output", side_effect=[REVISION, ""]
                ),
                mock.patch.object(clean_clone, "run_command", side_effect=fake_run) as run,
            ):
                self.assertTrue(clean_clone.validate(root))
            targets = [call.args[0][-1] for call in run.call_args_list if call.args[0][0] == "make"]
            self.assertEqual(targets, ["bootstrap", "doctor", "validate", "demo", "security"])
            self.assertNotIn("gate", targets)
            self.assertNotIn("clean-clone", targets)
            report = json.loads(
                (root / "evidence" / f"{REVISION[:12]}-clean-clone.json").read_text()
            )
            self.assertTrue(report["passed"])
            self.assertEqual(report["not_run"], [])
            self.assertTrue(all(item["passed"] for item in report["assertions"]))


if __name__ == "__main__":
    unittest.main()
