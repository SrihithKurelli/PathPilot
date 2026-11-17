"""Frozen, auditable final-campaign matrix planner (dry-run only)."""
from __future__ import annotations
import argparse
import itertools
import json
import platform
import subprocess
from pathlib import Path

from experiments.scenarios import SCENARIO_NAMES, build_scenario, scenario_digest

POLICIES = ("static", "least_loaded", "threshold", "stability_aware", "uncertainty_aware")
TELEMETRY_CONDITIONS = {
    "baseline": {"delay_s": 0.0, "noise_std": 0.0},
    "delayed": {"delay_s": 2.0, "noise_std": 0.0},
    "noisy": {"delay_s": 0.0, "noise_std": 0.05},
    "combined": {"delay_s": 2.0, "noise_std": 0.05},
}
INITIAL_PATHS = ("s1-s2-s4", "s1-s3-s4")


def build_manifest(*, repetitions=10, seed=2027, scenarios=None,
                   policies=None, conditions=None, initial_paths=None,
                   development=False):
    if repetitions < 1 or seed < 0:
        raise ValueError("repetitions must be positive and seed non-negative")
    scenarios = tuple(scenarios or SCENARIO_NAMES)
    policies = tuple(policies or POLICIES)
    conditions = tuple(conditions or TELEMETRY_CONDITIONS)
    initial_paths = tuple(initial_paths or INITIAL_PATHS)
    for value in scenarios:
        if value not in SCENARIO_NAMES:
            raise ValueError(f"unknown scenario: {value}")
    for value in policies:
        if value not in POLICIES:
            raise ValueError(f"unknown policy: {value}")
    for value in conditions:
        if value not in TELEMETRY_CONDITIONS:
            raise ValueError(f"unknown telemetry condition: {value}")
    for value in initial_paths:
        if value not in INITIAL_PATHS:
            raise ValueError(f"unknown initial path: {value}")

    rows = []
    for scenario, condition, initial, policy, repetition in itertools.product(
        scenarios, conditions, initial_paths, policies, range(1, repetitions + 1)
    ):
        # Same seed for all policies in a matched scenario/condition/path/repetition block.
        block_seed = seed + (SCENARIO_NAMES.index(scenario) * 100000) + (
            tuple(TELEMETRY_CONDITIONS).index(condition) * 10000
        ) + (INITIAL_PATHS.index(initial) * 1000) + repetition
        spec = build_scenario(scenario, seed=block_seed)
        rows.append({
            "scenario": scenario,
            "scenario_sha256": scenario_digest(spec),
            "telemetry_condition": condition,
            **TELEMETRY_CONDITIONS[condition],
            "initial_bottleneck_path": initial,
            "policy": policy,
            "repetition": repetition,
            "workload_seed": block_seed,
            "split": "development" if development else "final_test",
        })
    revision_result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    status_result = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, check=False
    )
    git_revision = revision_result.stdout.strip() if revision_result.returncode == 0 else "unknown"
    git_dirty = int(bool(status_result.stdout.strip())) if status_result.returncode == 0 else -1
    if not development and (git_revision == "unknown" or git_dirty != 0):
        raise ValueError("final-test manifest requires a known revision and clean working tree")
    estimated_seconds = sum(
        build_scenario(row["scenario"], seed=row["workload_seed"]).duration_s
        + max(6.0, row["delay_s"] + 4.0) + 7.0
        for row in rows
    )
    return {
        "schema_version": 1,
        "git_revision": git_revision,
        "git_worktree_dirty": git_dirty,
        "python_version": platform.python_version(),
        "campaign": "pathpilot_proposal_final" if not development else "pathpilot_development",
        "seed_base": seed,
        "repetitions_per_cell": repetitions,
        "policies": list(policies),
        "scenarios": list(scenarios),
        "telemetry_conditions": list(conditions),
        "initial_paths": list(initial_paths),
        "trial_count": len(rows),
        "estimated_runtime_seconds_lower_bound": estimated_seconds,
        "estimated_runtime_hours_lower_bound": round(estimated_seconds / 3600, 2),
        "matched_policy_seed_rule": "same workload seed within scenario/condition/initial-path/repetition block",
        "development_workloads_must_not_be_mixed_with_final_test": True,
        "trials": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=10)
    parser.add_argument("--seed", type=int, default=2027)
    parser.add_argument("--development", action="store_true")
    parser.add_argument("--output", type=Path,
                        default=Path("results/final_campaign_manifest.json"))
    args = parser.parse_args()
    manifest = build_manifest(repetitions=args.repetitions, seed=args.seed,
                              development=args.development)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"Dry-run manifest: {args.output}")
    print(f"Policies: {len(manifest['policies'])}")
    print(f"Scenarios: {len(manifest['scenarios'])}")
    print(f"Telemetry conditions: {len(manifest['telemetry_conditions'])}")
    print(f"Initial paths: {len(manifest['initial_paths'])}")
    print(f"Repetitions per cell: {args.repetitions}")
    print(f"Planned trials: {manifest['trial_count']}")
    print("No Mininet or controller processes were started.")


if __name__ == "__main__":
    main()
