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
    previous_path=None,
    noise_margin_sigma=1.0,
):
    if not telemetry:
        raise ValueError("at least one candidate path is required")
    if noise_margin_sigma < 0 or not math.isfinite(noise_margin_sigma):
        raise ValueError("noise_margin_sigma must be finite and non-negative")
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
        candidates = eligible or names

        # Even a fresh sample can contain substantial measurement noise.
        # Compare the two best candidates against the uncertainty of their
        # difference before trusting a small utilization ranking.
        if len(candidates) > 1:
            ranked = sorted(candidates, key=lambda n: telemetry[n].utilization)
            best, second = ranked[0], ranked[1]
            combined_uncertainty = math.hypot(
                telemetry[best].variability,
                telemetry[second].variability,
            )
            margin = noise_margin_sigma * combined_uncertainty
            if telemetry[second].utilization - telemetry[best].utilization <= margin:
                # If the measurements cannot distinguish the paths, avoid
                # repeatedly sending new flows down the previous path.
                alternatives = [n for n in candidates if n != previous_path]
                if previous_path in candidates and alternatives:
                    return alternatives[0]

        return min(
            candidates,
            key=lambda n: (
                telemetry[n].utilization,
                -confidence(telemetry[n]),
                n,
            ),
        )
    raise ValueError(f"unknown policy: {policy}")
