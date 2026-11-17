"""Deterministic workload scenario definitions for PathPilot evaluation."""
from __future__ import annotations
from dataclasses import asdict, dataclass
import hashlib
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


def build_scenario(name: str, *, seed: int = 7) -> Scenario:
    """Return a fixed workload schedule; seed is recorded and validated by caller.

    The current profiles are intentionally deterministic. Seeded variation is
    introduced at the campaign assignment layer, not by mutating a scenario
    after its identity has been recorded.
    """
    if seed < 0:
        raise ValueError("seed must be non-negative")
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
            FlowSpec("UDP", 10, 30, 10, "burst_path1"),
            FlowSpec("UDP", 10, 30, 25, "burst_path2"),
            FlowSpec("UDP", 10, 30, 40, "burst_path1"),
        ))
    if name == "mixed_short_long":
        short = tuple(FlowSpec("TCP", 2, 5, i * 1.0, "short") for i in range(12))
        long = tuple(FlowSpec("TCP", 45, 20, i * 0.5, "long") for i in range(3))
        return Scenario(name, 55, short + long)
    if name == "degrade_recover":
        return Scenario(name, 65, (
            FlowSpec("TCP", 60, 12, 0, "background"),
        ), (
            ImpairmentEvent(20, "s1-s2-s4", "set_rate", "5mbit"),
            ImpairmentEvent(40, "s1-s2-s4", "link_up"),
        ))
    if name == "link_loss_recovery":
        return Scenario(name, 65, (
            FlowSpec("TCP", 60, 12, 0, "background"),
        ), (
            ImpairmentEvent(20, "s1-s2-s4", "link_down"),
            ImpairmentEvent(40, "s1-s2-s4", "link_up"),
        ))
    raise KeyError(f"unknown scenario: {name}")


SCENARIO_NAMES = (
    "steady_low", "steady_high", "sudden_burst", "alternating_bursts",
    "mixed_short_long", "degrade_recover", "link_loss_recovery",
)


def scenario_digest(scenario: Scenario) -> str:
    payload = json.dumps(scenario.manifest(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
