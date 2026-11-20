#!/usr/bin/env python3
"""Deterministic synthetic telemetry replay for comparing PathPilot policies.

This is a policy-level simulation, not a Mininet traffic measurement. It
isolates selection behavior under controlled load and telemetry patterns.
Each replay step represents a configurable controller decision interval.
"""
from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

from controller.policies import Telemetry, choose_path, confidence

PATHS = ("s1-s2-s4", "s1-s3-s4")
POLICIES = ("static", "least_loaded", "threshold", "stability_aware", "uncertainty_aware")
SCENARIOS = (
    "balanced", "path1_hot", "path2_hot", "changing_load",
    "noisy_telemetry", "stale_telemetry", "steady_low", "steady_high",
    "burst", "alternating_burst", "link_degradation_recovery",
    "mixed_short_long",
)


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def scenario_state(name: str, step: int, rng: random.Random):
    """Return true path utilization and telemetry quality for one time step."""
    phase = step % 40
    if name == "balanced":
        truth = (0.35 + rng.uniform(-0.04, 0.04), 0.36 + rng.uniform(-0.04, 0.04))
        noise, age, variability = 0.015, 0.2, 0.02
    elif name == "path1_hot":
        truth = (0.88 + rng.uniform(-0.04, 0.04), 0.28 + rng.uniform(-0.04, 0.04))
        noise, age, variability = 0.02, 0.2, 0.02
    elif name == "path2_hot":
        truth = (0.25 + rng.uniform(-0.04, 0.04), 0.91 + rng.uniform(-0.04, 0.04))
        noise, age, variability = 0.02, 0.2, 0.02
    elif name == "changing_load":
        hot_first = phase < 20
        truth = ((0.86, 0.24) if hot_first else (0.24, 0.86))
        truth = tuple(clamp(x + rng.uniform(-0.05, 0.05)) for x in truth)
        noise, age, variability = 0.025, 0.3, 0.04
    elif name == "noisy_telemetry":
        truth = (0.48 + rng.uniform(-0.08, 0.08), 0.52 + rng.uniform(-0.08, 0.08))
        noise, age, variability = 0.18, 0.3, 0.48
    elif name == "stale_telemetry":
        truth = (0.18 + rng.uniform(-0.03, 0.03), 0.72 + rng.uniform(-0.03, 0.03))
        noise, age, variability = 0.03, 12.0, 0.12
    elif name == "steady_low":
        truth = (0.12 + rng.uniform(-0.02, 0.02), 0.15 + rng.uniform(-0.02, 0.02))
        noise, age, variability = 0.01, 0.2, 0.01
    elif name == "steady_high":
        truth = (0.82 + rng.uniform(-0.03, 0.03), 0.78 + rng.uniform(-0.03, 0.03))
        noise, age, variability = 0.02, 0.2, 0.02
    elif name == "burst":
        active = (step % 20) >= 10
        truth = (0.78, 0.30) if active else (0.25, 0.32)
        noise, age, variability = 0.025, 0.3, 0.05
    elif name == "alternating_burst":
        burst_path1 = (step // 8) % 2 == 0
        truth = (0.88, 0.25) if burst_path1 else (0.25, 0.88)
        noise, age, variability = 0.03, 0.3, 0.06
    elif name == "link_degradation_recovery":
        # Path 1 degrades at step 20 and recovers at step 50.
        if 20 <= step < 50:
            truth = (0.98, 0.25)
        else:
            truth = (0.25, 0.30)
        noise, age, variability = 0.02, 0.25, 0.03
    elif name == "mixed_short_long":
        # A changing aggregate-load proxy; this does not simulate individual flows.
        long_flow_load = 0.42 + 0.08 * (step % 30) / 30
        short_flow_burst = 0.35 if step % 5 == 0 else 0.04
        truth = (clamp(long_flow_load + short_flow_burst), clamp(long_flow_load + 0.08))
        noise, age, variability = 0.025, 0.3, 0.05
    else:
        raise ValueError(f"unknown scenario: {name}")
    return truth, noise, age, variability


def run_replay(seed: int, trials: int, steps: int, step_interval_s: float = 2.0):
    """Return per-decision policy records; all load patterns here are synthetic."""
    if step_interval_s <= 0:
        raise ValueError("step_interval_s must be positive")
    rows = []
    for scenario_index, scenario in enumerate(SCENARIOS):
        for trial in range(trials):
            rng = random.Random(seed + scenario_index * 100_003 + trial)
            previous_by_policy = {policy: None for policy in POLICIES}
            recent_paths = {policy: [] for policy in POLICIES}
            changes = {policy: 0 for policy in POLICIES}
            reversals = {policy: 0 for policy in POLICIES}
            for step in range(steps):
                truth, noise, age, variability = scenario_state(scenario, step, rng)
                observed = {}
                for index, path in enumerate(PATHS):
                    measured = clamp(truth[index] + rng.gauss(0, noise))
                    observed[path] = Telemetry(
                        utilization=measured,
                        age_s=max(0.0, age + rng.uniform(-0.05, 0.05)),
                        variability=clamp(variability + rng.uniform(-0.02, 0.02)),
                    )
                oracle_path = min(PATHS, key=lambda p: truth[PATHS.index(p)])
                oracle_util = min(truth)
                for policy in POLICIES:
                    previous_path = previous_by_policy[policy]
                    selected = choose_path(
                        observed, policy, threshold=0.75, min_confidence=0.5,
                        safe_fallback=PATHS[0], previous_path=previous_path,
                    )
                    path_history = recent_paths[policy]
                    route_changed = int(previous_path is not None and selected != previous_path)
                    reversed_recently = int(
                        len(path_history) >= 2 and selected == path_history[-2]
                        and selected != path_history[-1]
                    )
                    changes[policy] += route_changed
                    reversals[policy] += reversed_recently
                    path_history.append(selected)
                    previous_by_policy[policy] = selected
                    idx = PATHS.index(selected)
                    sample = observed[selected]
                    elapsed_s = (step + 1) * step_interval_s
                    rows.append({
                        "scenario": scenario, "trial": trial + 1, "step": step + 1,
                        "elapsed_s": round(elapsed_s, 3), "step_interval_s": step_interval_s,
                        "policy": policy, "selected_path": selected, "oracle_path": oracle_path,
                        "selected_true_utilization": round(truth[idx], 6),
                        "selected_observed_utilization": round(sample.utilization, 6),
                        "oracle_utilization": round(oracle_util, 6),
                        "regret": round(truth[idx] - oracle_util, 6),
                        "selected_confidence": round(confidence(sample), 6),
                        "oracle_choice": int(selected == oracle_path),
                        "route_changed": route_changed,
                        "reversal_to_previous_path": reversed_recently,
                        "path_changes_so_far": changes[policy],
                        "reversals_so_far": reversals[policy],
                        "path_changes_per_minute": round(changes[policy] * 60.0 / elapsed_s, 6),
                    })
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--step-interval-seconds", type=float, default=2.0)
    parser.add_argument("--output", type=Path, default=Path("results/policy_replay.csv"))
    args = parser.parse_args()
    if args.trials < 1 or args.steps < 1 or args.step_interval_seconds <= 0:
        parser.error("trials, steps and step interval must be positive")
    rows = run_replay(args.seed, args.trials, args.steps, args.step_interval_seconds)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} synthetic decisions to {args.output}")


if __name__ == "__main__":
    main()
