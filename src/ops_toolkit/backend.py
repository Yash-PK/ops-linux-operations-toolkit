"""Narrow OS boundary; fixtures replay inputs and never invoke live commands."""

import json
import os
import platform
import selectors
import shutil
import stat
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from .model import InvalidInput, Unavailable

MAX_INPUT = 1_048_576
COMMAND_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/opt/homebrew/bin"


def load_json(path):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise InvalidInput("JSON input contains duplicate object keys")
            result[key] = value
        return result

    try:
        # Nonblocking open + fstat prevent a FIFO/device input from hanging the CLI.
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        with os.fdopen(descriptor, encoding="utf-8") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise InvalidInput("JSON input must be a regular file, not a symlink or device")
            raw = handle.read(MAX_INPUT + 1)
        if len(raw) > MAX_INPUT:
            raise InvalidInput("JSON input exceeds 1 MiB")
        return json.loads(raw, object_pairs_hook=unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise InvalidInput("cannot read valid JSON input") from exc


class Backend:
    source = "live"

    def __init__(self, timeout=3.0, interval=0.1):
        self.timeout = timeout
        self.interval = interval
        self.platform = platform.system()

    def linux(self):
        if self.platform != "Linux":
            raise Unavailable("Linux source unavailable on this platform")

    def now(self):
        return datetime.now(timezone.utc)

    def cpu_count(self):
        return os.cpu_count() or 1

    def pause(self):
        time.sleep(self.interval)

    def read(self, path):
        try:
            with open(path, encoding="utf-8") as handle:
                data = handle.read(MAX_INPUT + 1)
            if len(data) > MAX_INPUT:
                raise Unavailable("source exceeds bounded read size")
            return data
        except (OSError, UnicodeError) as exc:
            raise Unavailable("source unreadable or denied") from exc

    def command(self, argv, accepted=(0,)):
        # Explicit argument vectors only: no shell, environment dump, or stderr replay.
        executable = shutil.which(argv[0], path=COMMAND_PATH)
        if not executable:
            raise Unavailable(f"{argv[0]} not installed")
        try:
            with subprocess.Popen(
                [executable, *argv[1:]],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env={"PATH": COMMAND_PATH, "LC_ALL": "C"},
            ) as process:
                try:
                    chunks, size = [], 0
                    deadline = time.monotonic() + self.timeout
                    with selectors.DefaultSelector() as selector:
                        selector.register(process.stdout, selectors.EVENT_READ)
                        while selector.get_map():
                            remaining = deadline - time.monotonic()
                            if remaining <= 0 or not selector.select(remaining):
                                raise subprocess.TimeoutExpired(argv[0], self.timeout)
                            chunk = os.read(process.stdout.fileno(), 65536)
                            if not chunk:
                                selector.unregister(process.stdout)
                                break
                            size += len(chunk)
                            if size > MAX_INPUT:
                                raise Unavailable(f"{argv[0]} output exceeds bounded result size")
                            chunks.append(chunk)
                    process.wait(timeout=max(0.001, deadline - time.monotonic()))
                    if process.returncode not in accepted:
                        raise Unavailable(
                            f"{argv[0]} exited {process.returncode}; details suppressed"
                        )
                    return b"".join(chunks).decode("utf-8")
                except BaseException:
                    if process.poll() is None:
                        process.kill()
                    process.wait()
                    raise
        except subprocess.TimeoutExpired as exc:
            raise Unavailable(f"{argv[0]} timed out") from exc
        except (OSError, UnicodeError) as exc:
            raise Unavailable(f"{argv[0]} could not run") from exc

    def which(self, name):
        return shutil.which(name, path=COMMAND_PATH) is not None

    def disk(self, path):
        try:
            data = os.statvfs(path)
        except OSError as exc:
            raise Unavailable("filesystem metadata unavailable") from exc
        return {
            key: getattr(data, key)
            for key in ("f_blocks", "f_bfree", "f_bavail", "f_frsize", "f_files", "f_ffree")
        }

    def metadata(self, path):
        try:
            value = Path(path).lstat()
        except OSError as exc:
            raise Unavailable("path metadata unavailable") from exc
        return {
            "mode": stat.S_IMODE(value.st_mode),
            "uid": value.st_uid,
            "gid": value.st_gid,
            "mtime": value.st_mtime,
            "regular": stat.S_ISREG(value.st_mode),
            "symlink": stat.S_ISLNK(value.st_mode),
        }

    def process_states(self):
        self.linux()
        states = []
        skipped = 0
        try:
            entries = list(Path("/proc").iterdir())
        except OSError as exc:
            raise Unavailable("process source unavailable") from exc
        for item in entries:
            if item.name.isdecimal():
                try:
                    data = self.read(item / "stat")
                    suffix = data[data.rindex(")") + 2 :].split()
                    if not suffix or len(suffix[0]) != 1:
                        raise ValueError("state")
                    states.append(suffix[0])
                except (Unavailable, ValueError):
                    skipped += 1
        return states, skipped

    def identity(self):
        result = {
            "uid": os.getuid(),
            "gid": os.getgid(),
            "supplementary_group_count": len(os.getgroups()),
        }
        if self.platform == "Linux":
            for kind, path in (
                ("local_user_count", "/etc/passwd"),
                ("local_group_count", "/etc/group"),
            ):
                result[kind] = sum(
                    1 for line in self.read(path).splitlines() if line and not line.startswith("#")
                )
        return result

    def entries(self, path):
        try:
            return [item.name for item in Path(path).iterdir()]
        except FileNotFoundError:
            return []
        except OSError as exc:
            raise Unavailable("directory inventory denied") from exc


class FixtureBackend(Backend):
    source = "fixture"

    def __init__(self, data, timeout=3.0, interval=0.1):
        super().__init__(timeout, interval)
        if (
            not isinstance(data, dict)
            or type(data.get("fixture_schema")) is not int
            or data.get("fixture_schema") != 1
        ):
            raise InvalidInput("fixture requires fixture_schema 1")
        self.validate_fixture(data)
        self.data = data
        self.platform = data.get("platform", "Linux")
        self.offsets = {}

    @staticmethod
    def validate_fixture(data):
        from .model import number

        def reject():
            raise InvalidInput("fixture contains malformed nested input data")

        if not isinstance(data.get("platform", "Linux"), str):
            reject()
        for key in ("files", "commands", "disks", "metadata", "identity", "directories"):
            if not isinstance(data.get(key, {}), dict):
                reject()
        for value in data.get("files", {}).values():
            if not isinstance(value, str) and not (
                isinstance(value, list) and value and all(isinstance(item, str) for item in value)
            ):
                reject()
        for value in data.get("commands", {}).values():
            if not isinstance(value, dict) or set(value) - {"stdout", "returncode", "timeout"}:
                reject()
            if (
                not isinstance(value.get("stdout", ""), str)
                or type(value.get("returncode", 0)) is not int
                or type(value.get("timeout", False)) is not bool
            ):
                reject()
        disk_keys = {"f_blocks", "f_bfree", "f_bavail", "f_frsize", "f_files", "f_ffree"}
        for value in data.get("disks", {}).values():
            if not isinstance(value, dict) or set(value) != disk_keys:
                reject()
            for item in value.values():
                number(item, "fixture filesystem counter")
        for value in data.get("metadata", {}).values():
            if not isinstance(value, dict) or set(value) != {
                "mode",
                "uid",
                "gid",
                "mtime",
                "regular",
                "symlink",
            }:
                reject()
            if any(type(value[key]) is not bool for key in ("regular", "symlink")):
                reject()
            for key in ("mode", "uid", "gid"):
                if type(value[key]) is not int:
                    reject()
                number(value[key], "fixture metadata")
            number(value["mode"], "fixture mode", 0, 0o7777)
            number(value["mtime"], "fixture mtime")
        identity_keys = {
            "uid",
            "gid",
            "supplementary_group_count",
            "local_user_count",
            "local_group_count",
        }
        if set(data.get("identity", {})) - identity_keys:
            reject()
        for value in data.get("identity", {}).values():
            if type(value) is not int or value < 0:
                reject()
        for key in ("tools", "process_states"):
            value = data.get(key, [])
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                reject()
        for value in data.get("directories", {}).values():
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                reject()
        for key in ("cpu_count", "process_skipped"):
            if type(data.get(key, 1)) is not int or data.get(key, 1) < (
                1 if key == "cpu_count" else 0
            ):
                reject()

    def now(self):
        try:
            value = datetime.fromisoformat(self.data["now"].replace("Z", "+00:00"))
            if value.tzinfo is None:
                raise ValueError("timezone missing")
            return value.astimezone(timezone.utc)
        except (KeyError, ValueError, AttributeError) as exc:
            raise InvalidInput("fixture requires valid UTC now") from exc

    def cpu_count(self):
        value = self.data.get("cpu_count", 2)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise InvalidInput("invalid fixture cpu_count")
        return value

    def pause(self):
        pass

    def read(self, path):
        value = self.data.get("files", {}).get(str(path))
        if isinstance(value, list):
            offset = self.offsets.get(str(path), 0)
            self.offsets[str(path)] = offset + 1
            if offset >= len(value):
                raise Unavailable("fixture snapshots exhausted")
            value = value[offset]
        if not isinstance(value, str):
            raise Unavailable("source absent in fixture")
        return value

    def command(self, argv, accepted=(0,)):
        value = self.data.get("commands", {}).get(" ".join(argv))
        if value is None:
            raise Unavailable(f"{argv[0]} absent in fixture")
        if value.get("timeout"):
            raise Unavailable(f"{argv[0]} timed out")
        if value.get("returncode", 0) not in accepted:
            raise Unavailable(f"{argv[0]} failed in fixture")
        return value.get("stdout", "")

    def which(self, name):
        return name in self.data.get("tools", [])

    def disk(self, path):
        try:
            return self.data["disks"][path]
        except KeyError as exc:
            raise Unavailable("filesystem absent in fixture") from exc

    def metadata(self, path):
        try:
            return self.data["metadata"][path]
        except KeyError as exc:
            raise Unavailable("path absent in fixture") from exc

    def process_states(self):
        self.linux()
        if "process_states" not in self.data:
            raise Unavailable("process source absent in fixture")
        return self.data["process_states"], self.data.get("process_skipped", 0)

    def identity(self):
        if "identity" not in self.data:
            raise Unavailable("identity absent in fixture")
        return self.data["identity"]

    def entries(self, path):
        return self.data.get("directories", {}).get(path, [])
