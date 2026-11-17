"""Deterministic workload scenario definitions for PathPilot evaluation."""
from __future__ import annotations
from dataclasses import asdict, dataclass, replace
import hashlib
import random
import json


@dataclass(frozen=True)
class FlowSpec:
    protocol: str
    duration_s: float
    offered_rate_mbps: float
    start_offset_s: float
    flow_class: str
    direction: str = "h1_to_h2"
    payload_bytes: int = 1200

    def __post_init__(self):
        if self.protocol not in {"TCP", "UDP"}:
            raise ValueError("protocol must be TCP or UDP")
        if self.duration_s <= 0 or self.offered_rate_mbps < 0 or self.start_offset_s < 0:
            raise ValueError("invalid flow timing or offered rate")
        if self.payload_bytes < 1:
            raise ValueError("payload_bytes must be positive")


@dataclass(frozen=True)
class ImpairmentEvent:
    offset_s: float
    path: str
    action: str
    value: str = ""

    def __post_init__(self):
        if self.offset_s < 0:
            raise ValueError("event offset must be non-negative")
        if self.path not in {"s1-s2-s4", "s1-s3-s4", "both"}:
            raise ValueError("unknown path")
        if self.action not in {"set_rate", "set_delay", "set_loss", "link_down", "link_up"}:
            raise ValueError("unknown impairment action")


@dataclass(frozen=True)
class Scenario:
    name: str
    duration_s: float
    flows: tuple[FlowSpec, ...]
    impairments: tuple[ImpairmentEvent, ...] = ()

    def __post_init__(self):
        if self.duration_s <= 0:
            raise ValueError("scenario duration must be positive")
        for flow in self.flows:
            if flow.start_offset_s + flow.duration_s > self.duration_s:
                raise ValueError("flow extends beyond scenario duration")
        if any(event.offset_s > self.duration_s for event in self.impairments):
            raise ValueError("impairment event extends beyond scenario duration")

    def manifest(self):
        return {
            "name": self.name,
            "duration_s": self.duration_s,
            "flows": [asdict(flow) for flow in self.flows],
            "impairments": [asdict(event) for event in self.impairments],
        }


def _base_scenario(name: str) -> Scenario:
    """Return the unperturbed base schedule for a scenario."""
    low = (FlowSpec("TCP", 50, 8, 0, "background"),)
    high = tuple(FlowSpec("TCP", 45, 30, i * 0.25, "background") for i in range(4))
    if name == "steady_low":
        return Scenario(name, 55, low)
    if name == "steady_high":
        return Scenario(name, 55, high)
    if name == "sudden_burst":
        return Scenario(name, 60, (
            FlowSpec("TCP", 55, 8, 0, "background"),
            FlowSpec("UDP", 12, 35, 20, "burst"),
        ))
    if name == "alternating_bursts":
        return Scenario(name, 70, (
            FlowSpec("TCP", 65, 8, 0, "background"),
            FlowSpec("UDP", 10, 30, 10, "burst_phase_a"),
            FlowSpec("UDP", 10, 30, 25, "burst_phase_b"),
            FlowSpec("UDP", 10, 30, 40, "burst_phase_a"),
        ))
    if name == "mixed_short_long":
        short = tuple(FlowSpec("TCP", 2, 5, i * 1.0, "short") for i in range(12))
        long = tuple(FlowSpec("TCP", 45, 20, i * 0.5, "long") for i in range(3))
        return Scenario(name, 55, short + long)
    if name == "degrade_recover":
        return Scenario(name, 65, (
            FlowSpec("TCP", 60, 12, 0, "background"),
            FlowSpec("TCP", 10, 8, 25, "during_degradation"),
            FlowSpec("TCP", 10, 8, 45, "after_recovery"),
        ), (
            ImpairmentEvent(20, "s1-s2-s4", "set_rate", "5mbit"),
            ImpairmentEvent(40, "s1-s2-s4", "set_rate", "100mbit"),
        ))
    if name == "link_loss_recovery":
        return Scenario(name, 65, (
            FlowSpec("TCP", 60, 12, 0, "background"),
            FlowSpec("TCP", 10, 8, 25, "during_link_loss"),
            FlowSpec("TCP", 10, 8, 45, "after_link_recovery"),
        ), (
            ImpairmentEvent(20, "s1-s2-s4", "link_down"),
            ImpairmentEvent(40, "s1-s2-s4", "link_up"),
        ))
    if name == "loss_recovery":
        return Scenario(name, 65, (
            FlowSpec("TCP", 60, 12, 0, "background"),
            FlowSpec("TCP", 10, 8, 25, "during_packet_loss"),
            FlowSpec("TCP", 10, 8, 45, "after_packet_loss"),
        ), (
            ImpairmentEvent(20, "s1-s2-s4", "set_loss", "5%"),
            ImpairmentEvent(40, "s1-s2-s4", "set_loss", "0%"),
        ))
    raise KeyError(f"unknown scenario: {name}")


def build_scenario(name: str, *, seed: int = 7) -> Scenario:
    """Create deterministic, seed-specific workload timing/rate variation.

    Matched policies receive the same seed and therefore the same offered load.
    Perturbations are deliberately small (±2% rate, ±50 ms start/event timing)
    and are recorded through the scenario digest in the run manifest.
    """
    if seed < 0:
        raise ValueError("seed must be non-negative")
    base = _base_scenario(name)
    rng = random.Random(seed)
    flows = tuple(replace(
        flow,
        offered_rate_mbps=round(flow.offered_rate_mbps * rng.uniform(.98, 1.02), 5),
        start_offset_s=max(0.0, flow.start_offset_s + rng.uniform(-.05, .05)),
    ) for flow in base.flows)
    events = tuple(replace(
        event, offset_s=max(0.0, event.offset_s + rng.uniform(-.05, .05))
    ) for event in base.impairments)
    return Scenario(base.name, base.duration_s, flows, events)


SCENARIO_NAMES = (
    "steady_low", "steady_high", "sudden_burst", "alternating_bursts",
    "mixed_short_long", "degrade_recover", "link_loss_recovery", "loss_recovery",
)


def scenario_digest(scenario: Scenario) -> str:
    payload = json.dumps(scenario.manifest(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
