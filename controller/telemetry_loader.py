"""Validated loading and fallback values for controller telemetry."""
import json
from pathlib import Path

from controller.policies import Telemetry


EXPECTED_PATHS = ("s1-s2-s4", "s1-s3-s4")
EXPECTED_FIELDS = {"utilization", "age_s", "variability"}


def load_static_telemetry(path):
    """Load a complete, validated static telemetry snapshot.

    Raises ValueError for malformed or incomplete data. Callers should then
    use conservative_telemetry() rather than passing partial data to a policy.
    """
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read valid telemetry JSON: {exc}") from exc

    if not isinstance(raw, dict) or set(raw) != set(EXPECTED_PATHS):
        raise ValueError(
            "telemetry must contain exactly these paths: "
            + ", ".join(EXPECTED_PATHS)
        )

    telemetry = {}
    for path_name in EXPECTED_PATHS:
        values = raw[path_name]
        if not isinstance(values, dict) or set(values) != EXPECTED_FIELDS:
            raise ValueError(
                f"{path_name} must contain exactly: "
                + ", ".join(sorted(EXPECTED_FIELDS))
            )
        try:
            sample = Telemetry(**values)
            sample.validate()
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid telemetry for {path_name}: {exc}") from exc
        telemetry[path_name] = sample
    return telemetry


def conservative_telemetry():
    """Return deliberately untrusted samples when no usable source exists."""
    return {
        "s1-s2-s4": Telemetry(0.5, 999.0, 1.0),
        "s1-s3-s4": Telemetry(0.5, 999.0, 1.0),
    }
