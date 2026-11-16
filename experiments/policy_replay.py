#!/usr/bin/env python3
"""Deterministic synthetic telemetry replay for comparing PathPilot policies.

This is a policy-level simulation, not a Mininet measurement. It isolates
selection behavior under controlled telemetry quality and load patterns.
"""
from __future__ import annotations

import argparse
import csv
import random
import statistics
from pathlib import Path

from controller.policies import Telemetry, choose_path, confidence

PATHS = ("s1-s2-s4", "s1-s3-s4")
POLICIES = ("static", "least_loaded", "threshold", "stability_aware", "uncertainty_aware")


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def scenario_state(name: str, step: int, rng: random.Random):
    """Return true utilization and telemetry quality for one time step."""
    phase = step % 40
    if name == "balanced":
        truth = (0.35 + rng.uniform(-0.04, 0.04),
                 0.36 + rng.uniform(-0.04, 0.04))
        noise, age, variability = 0.015, 0.2, 0.02
    elif name == "path1_hot":
        truth = (0.88 + rng.uniform(-0.04, 0.04),
                 0.28 + rng.uniform(-0.04, 0.04))
        noise, age, variability = 0.02, 0.2, 0.02
    elif name == "path2_hot":
        truth = (0.25 + rng.uniform(-0.04, 0.04),
                 0.91 + rng.uniform(-0.04, 0.04))
        noise, age, variability = 0.02, 0.2, 0.02
    elif name == "changing_load":
        hot_first = phase < 20
        truth = ((0.86, 0.24) if hot_first else (0.24, 0.86))
        truth = tuple(clamp(x + rng.uniform(-0.05, 0.05)) for x in truth)
        noise, age, variability = 0.025, 0.3, 0.04
    elif name == "noisy_telemetry":
        truth = (0.48 + rng.uniform(-0.08, 0.08),
                 0.52 + rng.uniform(-0.08, 0.08))
        noise, age, variability = 0.18, 0.3, 0.48
    elif name == "stale_telemetry":
        truth = (0.18 + rng.uniform(-0.03, 0.03),
                 0.72 + rng.uniform(-0.03, 0.03))
        noise, age, variability = 0.03, 12.0, 0.12
    else:
        raise ValueError(f"unknown scenario: {name}")
    return truth, noise, age, variability


def run_replay(seed: int, trials: int, steps: int):
    scenarios = ("balanced", "path1_hot", "path2_hot",
                 "changing_load", "noisy_telemetry", "stale_telemetry")
    rows = []
    for scenario_index, scenario in enumerate(scenarios):
        for trial in range(trials):
            rng = random.Random(seed + scenario_index * 100_003 + trial)
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
                    selected = choose_path(
                        observed, policy, threshold=0.75,
                        min_confidence=0.5, safe_fallback=PATHS[0],
                    )
                    idx = PATHS.index(selected)
                    sample = observed[selected]
                    rows.append({
                        "scenario": scenario,
                        "trial": trial + 1,
                        "step": step + 1,
                        "policy": policy,
                        "selected_path": selected,
                        "oracle_path": oracle_path,
                        "selected_true_utilization": round(truth[idx], 6),
                        "selected_observed_utilization": round(sample.utilization, 6),
                        "oracle_utilization": round(oracle_util, 6),
                        "regret": round(truth[idx] - oracle_util, 6),
                        "selected_confidence": round(confidence(sample), 6),
                        "oracle_choice": int(selected == oracle_path),
                    })
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--output", type=Path, default=Path("results/policy_replay.csv"))
    args = parser.parse_args()
    if args.trials < 1 or args.steps < 1:
        parser.error("--trials and --steps must be positive")
    rows = run_replay(args.seed, args.trials, args.steps)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} decisions to {args.output}")


if __name__ == "__main__":
    main()
