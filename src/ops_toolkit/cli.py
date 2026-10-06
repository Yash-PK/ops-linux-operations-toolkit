"""Stable CLI with read-only defaults and explicit unsupported results."""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

from . import __version__
from .backend import Backend, FixtureBackend, load_json
from .collectors import DEFAULT_HEALTH, HEALTH_NAMES, INSPECT_NAMES, health, inspect
from .model import InvalidInput, exit_code, number, thresholds


def csv_names(value, choices):
    names = value.split(",")
    if not names or any(name not in choices for name in names) or len(names) != len(set(names)):
        raise InvalidInput("list must contain distinct supported names separated by commas")
    return names


def parser():
    result = argparse.ArgumentParser(
        description="Unprivileged read-only health and metadata checks. No remediation or remote probes."
    )
    result.add_argument("--version", action="version", version=__version__)
    sub = result.add_subparsers(dest="command", required=True)
    for name in ("health", "inspect"):
        current = sub.add_parser(name)
        current.add_argument("--format", choices=("json", "text"), default="text")
        current.add_argument(
            "--fixture", help="replay synthetic inputs; never invokes live collectors"
        )
        current.add_argument(
            "--timeout", type=float, default=3, help="external command deadline in seconds, 0.1–60"
        )
        current.add_argument("--verbose", action="store_true", help="summary-only stderr logging")
        if name == "health":
            current.add_argument(
                "--checks", default=",".join(DEFAULT_HEALTH), help=",".join(HEALTH_NAMES)
            )
            current.add_argument("--config", help='JSON: {"thresholds": {"cpu_pct": 85}}')
            current.add_argument("--threshold", action="append", default=[], metavar="NAME=NUMBER")
            current.add_argument(
                "--interval", type=float, default=0.1, help="CPU sample interval, 0.01–5 seconds"
            )
            current.add_argument("--disk-path", default="/")
            current.add_argument(
                "--service", action="append", default=[], help="explicit systemd unit (repeatable)"
            )
            current.add_argument(
                "--certificate", help="explicit PEM certificate file; no network connection"
            )
            current.add_argument(
                "--backup", help="explicit backup file; mtime only, no contents read"
            )
        else:
            current.add_argument(
                "--sections", default="paths,identity,tools", help=",".join(INSPECT_NAMES)
            )
            current.add_argument(
                "--path", action="append", default=[], help="explicit metadata path (repeatable)"
            )
            current.add_argument(
                "--acl", action="store_true", help="also inspect ACL entries using Linux getfacl"
            )
    return result


def path_input(value):
    if value is None:
        return
    if (
        not value
        or value.startswith("-")
        or "\x00" in value
        or any(ord(char) < 32 for char in value)
    ):
        raise InvalidInput(
            "paths must be nonempty, without control characters or leading '-' (use ./)"
        )
    # Resolve no symlinks and do not read the target during argument validation.
    Path(value)


def validate(args):
    path_input(args.fixture)
    args.timeout = number(args.timeout, "timeout", 0.1, 60)
    if args.command == "health":
        path_input(args.config)
        args.interval = number(args.interval, "interval", 0.01, 5)
        args.checks = csv_names(args.checks, HEALTH_NAMES)
        config = load_json(args.config) if args.config else {}
        policy = thresholds(config)
        for override in args.threshold:
            try:
                key, value = override.split("=", 1)
                policy[key] = float(value)
            except ValueError as exc:
                raise InvalidInput("threshold must be NAME=NUMBER") from exc
        policy = thresholds({"thresholds": policy})
        for unit in args.service:
            if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.@:-]{0,246}\.service", unit):
                raise InvalidInput("service must be an explicit .service unit name")
        if "services" in args.checks and not args.service:
            raise InvalidInput("services check requires --service")
        if len(args.service) != len(set(args.service)):
            raise InvalidInput("duplicate service units")
        for name in ("certificate", "backup"):
            if name in args.checks and not getattr(args, name):
                raise InvalidInput(f"{name} check requires --{name}")
        for value in (args.disk_path, args.certificate, args.backup):
            path_input(value)
        return policy
    args.sections = csv_names(args.sections, INSPECT_NAMES)
    for value in args.path:
        path_input(value)
    if args.acl and ("paths" not in args.sections or not args.path):
        raise InvalidInput("--acl requires paths section and --path")
    if args.sections == ["paths"] and not args.path:
        raise InvalidInput("paths-only inspection requires --path")
    return None


def render(report, fmt, stream):
    if fmt == "json":
        print(json.dumps(report, sort_keys=True, indent=2, allow_nan=False), file=stream)
        return
    print(
        f"ops-toolkit {report['version']} | source={report['source']} | platform={report['platform']}",
        file=stream,
    )
    for check in report["checks"]:
        print(f"[{check['status']}] {check['name']}: {check['message']}", file=stream)
        if check["metrics"]:
            print("  " + json.dumps(check["metrics"], sort_keys=True), file=stream)
    print(f"exit={report['exit_code']} (0=OK, 1=degraded, 2=invalid, 3=unavailable)", file=stream)


def main(argv=None, stdout=None, stderr=None):
    stdout, stderr = stdout or sys.stdout, stderr or sys.stderr
    args = parser().parse_args(argv)
    logger = logging.getLogger("ops_toolkit")
    logger.handlers.clear()
    logger.propagate = False
    handler = logging.StreamHandler(stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO if args.verbose else logging.WARNING)
    try:
        policy = validate(args)
        backend = (
            FixtureBackend(load_json(args.fixture), args.timeout, getattr(args, "interval", 0.1))
            if args.fixture
            else Backend(args.timeout, getattr(args, "interval", 0.1))
        )
        timestamp = backend.now().isoformat()
        checks = (
            health(backend, args, policy) if args.command == "health" else inspect(backend, args)
        )
        code = exit_code(checks)
        report = {
            "schema_version": 1,
            "version": __version__,
            "source": backend.source,
            "platform": backend.platform,
            "timestamp": timestamp,
            "checks": [check.to_dict() for check in checks],
            "exit_code": code,
        }
        render(report, args.format, stdout)
        logger.info(
            "completed command=%s checks=%d exit=%d source=%s",
            args.command,
            len(checks),
            code,
            backend.source,
        )
        return code
    except InvalidInput as exc:
        if args.format == "json":
            print(
                json.dumps(
                    {
                        "schema_version": 1,
                        "error": "invalid input",
                        "message": str(exc),
                        "exit_code": 2,
                    }
                ),
                file=stdout,
            )
        else:
            print(f"invalid input: {exc}", file=stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
