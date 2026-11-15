"""Pure policy logic, independent of Mininet and Ryu."""
from dataclasses import dataclass
import math
from typing import Mapping


@dataclass(frozen=True)
class Telemetry:
    utilization: float
    age_s: float
    variability: float

    def validate(self):
        if not 0 <= self.utilization <= 1:
            raise ValueError("utilization must be in [0,1]")
        if self.age_s < 0 or not math.isfinite(self.age_s):
            raise ValueError("age_s must be finite and >= 0")
        if not 0 <= self.variability <= 1:
            raise ValueError("variability must be in [0,1]")


def confidence(sample: Telemetry, alpha=0.5, beta=2.0):
    sample.validate()
    if alpha < 0 or beta < 0:
        raise ValueError("alpha and beta must be non-negative")
    return math.exp(-alpha * sample.age_s - beta * sample.variability)


def choose_path(
    telemetry: Mapping[str, Telemetry],
    policy="least_loaded",
    *,
    threshold=0.75,
    min_confidence=0.5,
    safe_fallback=None,
):
    if not telemetry:
        raise ValueError("at least one candidate path is required")
    names = sorted(telemetry)
    for sample in telemetry.values():
        sample.validate()

    if policy == "static":
        return names[0]
    if policy == "least_loaded":
        return min(names, key=lambda n: (telemetry[n].utilization, n))
    if policy == "threshold":
        eligible = [n for n in names if telemetry[n].utilization <= threshold]
        return min(eligible or names, key=lambda n: (telemetry[n].utilization, n))
    if policy == "uncertainty_aware":
        eligible = [
            n for n in names
            if confidence(telemetry[n]) >= min_confidence
        ]
        # If every sample is below the confidence threshold, avoid a fixed
        # path choice: use the least-loaded estimate as the best available
        # fallback while retaining uncertainty-aware filtering when possible.
        candidates = eligible or names
        return min(
            candidates,
            key=lambda n: (
                telemetry[n].utilization,
                -confidence(telemetry[n]),
                n,
            ),
        )
    raise ValueError(f"unknown policy: {policy}")
