"""Policy validation and stable output model."""

import math
from dataclasses import asdict, dataclass, field

DEFAULTS = {
    "cpu_pct": 85.0,
    "memory_pct": 85.0,
    "disk_pct": 85.0,
    "inodes_pct": 85.0,
    "load_per_cpu": 1.0,
    "process_count": 1000.0,
    "certificate_days": 14.0,
    "backup_hours": 24.0,
}


class InvalidInput(ValueError):
    """A user-supplied value is invalid."""


class Unavailable(RuntimeError):
    """A source, tool, privilege or supported platform is unavailable."""


@dataclass
class Check:
    name: str
    status: str
    message: str
    metrics: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


def number(value, name, minimum=0.0, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidInput(f"{name} must be a number")
    if not math.isfinite(value) or value < minimum:
        raise InvalidInput(f"{name} must be finite and >= {minimum}")
    if maximum is not None and value > maximum:
        raise InvalidInput(f"{name} must be <= {maximum}")
    return float(value)


def thresholds(config):
    if not isinstance(config, dict) or set(config) - {"thresholds"}:
        raise InvalidInput("config must contain only a thresholds object")
    overrides = config.get("thresholds", {})
    if not isinstance(overrides, dict) or set(overrides) - set(DEFAULTS):
        raise InvalidInput("unknown threshold or invalid thresholds object")
    result = DEFAULTS.copy()
    for key, value in overrides.items():
        result[key] = number(value, key, 0, 100 if key.endswith("_pct") else None)
    return result


def exit_code(checks):
    if any(check.status == "UNKNOWN" for check in checks):
        return 3
    if any(check.status == "WARN" for check in checks):
        return 1
    return 0


def threshold_check(name, value, limit, metric, *, below=False, metrics=None):
    degraded = value <= limit if below else value >= limit
    values = dict(metrics or {})
    values[metric] = round(value, 3)
    values["warning_threshold"] = limit
    return Check(
        name,
        "WARN" if degraded else "OK",
        "threshold reached" if degraded else "within threshold",
        values,
    )
