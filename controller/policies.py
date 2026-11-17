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
        values = {
            "utilization": self.utilization,
            "age_s": self.age_s,
            "variability": self.variability,
        }
        for name, value in values.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be a real number")
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if not 0 <= self.utilization <= 1:
            raise ValueError("utilization must be in [0,1]")
        if self.age_s < 0:
            raise ValueError("age_s must be >= 0")
        if not 0 <= self.variability <= 1:
            raise ValueError("variability must be in [0,1]")


def confidence(sample: Telemetry, alpha=0.5, beta=2.0):
    sample.validate()
    if alpha < 0 or beta < 0 or not math.isfinite(alpha + beta):
        raise ValueError("alpha and beta must be finite and non-negative")
    return math.exp(-alpha * sample.age_s - beta * sample.variability)


def next_round_robin_fallback(telemetry: Mapping[str, Telemetry], previous_path=None):
    """Choose the next sorted path, rotating across successive uncertain decisions."""
    names = sorted(telemetry)
    if not names:
        raise ValueError("at least one candidate path is required")
    if previous_path not in names:
        return names[0]
    return names[(names.index(previous_path) + 1) % len(names)]


def choose_path(
    telemetry: Mapping[str, Telemetry],
    policy="least_loaded",
    *,
    threshold=0.75,
    min_confidence=0.5,
    safe_fallback=None,
    previous_path=None,
    noise_margin_sigma=1.0,
    switch_margin=0.10,
):
    if not telemetry:
        raise ValueError("at least one candidate path is required")
    if noise_margin_sigma < 0 or not math.isfinite(noise_margin_sigma):
        raise ValueError("noise_margin_sigma must be finite and non-negative")
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be in [0,1]")
    if not 0 <= min_confidence <= 1:
        raise ValueError("min_confidence must be in [0,1]")
    if switch_margin < 0 or not math.isfinite(switch_margin):
        raise ValueError("switch_margin must be finite and non-negative")
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
    if policy == "stability_aware":
        best = min(names, key=lambda n: (telemetry[n].utilization, n))
        # Baseline rule: retain the previous path unless another path improves
        # measured utilization by at least switch_margin (absolute fraction).
        # This is a comparator, not PathPilot's proposed confidence mechanism.
        if previous_path in telemetry and previous_path != best:
            improvement = (
                telemetry[previous_path].utilization - telemetry[best].utilization
            )
            if improvement < switch_margin:
                return previous_path
        return best
    if policy == "uncertainty_aware":
        eligible = [
            n for n in names
            if confidence(telemetry[n]) >= min_confidence
        ]
        # If every sample is below the confidence threshold, measured load is
        # not trustworthy enough to rank paths. Honor an explicit deterministic
        # fallback when the caller has one; otherwise retain least-loaded
        # behavior for backwards compatibility with standalone callers.
        if not eligible and safe_fallback in names:
            return safe_fallback
        candidates = eligible or names
        if len(candidates) > 1:
            ranked = sorted(candidates, key=lambda n: telemetry[n].utilization)
            best, second = ranked[0], ranked[1]
            combined_uncertainty = math.hypot(
                telemetry[best].variability,
                telemetry[second].variability,
            )
            margin = noise_margin_sigma * combined_uncertainty
            if telemetry[second].utilization - telemetry[best].utilization <= margin:
                alternatives = [n for n in candidates if n != previous_path]
                if previous_path in candidates and alternatives:
                    return alternatives[0]
                # With no previous route, use the caller's deterministic
                # fallback instead of always favoring the alphabetically first
                # path when measurements are indistinguishable.
                if previous_path not in candidates and safe_fallback in candidates:
                    return safe_fallback
        return min(
            candidates,
            key=lambda n: (
                telemetry[n].utilization,
                -confidence(telemetry[n]),
                n,
            ),
        )
    raise ValueError(f"unknown policy: {policy}")
