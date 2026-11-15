#!/usr/bin/env python3
"""Run the complete controlled telemetry-impairment Mininet experiment matrix.

Run as root from the repository root on the Ubuntu/Mininet host. Each condition
runs all four policies for the requested number of trials. Raw CSV files are
written per condition so completed conditions remain available if a later
condition fails.
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics
import subprocess
import sys
from pathlib import Path

POLICIES = ("static", "least_loaded", "threshold", "uncertainty_aware")
CONDITIONS = {
    "baseline": (0.0, 0.0),
    "delayed": (2.0, 0.0),
    "noisy": (0.0, 0.05),
    "combined": (2.0, 0.05),
    "severe_combined": (4.0, 0.10),
}
RAW_FIELDS = (
    "condition", "policy", "trial", "seed", "telemetry_delay_seconds",
    "telemetry_noise_std", "connectivity_loss_pct", "first_flow_path",
    "bottleneck_path", "bottleneck_interface", "bottleneck_rate",
    "second_flow_path", "avoided_bottleneck", "second_flow_mbps",
    "first_flow_mbps", "warmup_seconds", "first_selection_log",
    "second_selection_log", "first_telemetry_log", "second_telemetry_log",
)


def summarize(rows):
    groups = {}
    for row in rows:
        groups.setdefault((row["condition"], row["policy"]), []).append(row)

    result = []
    for (condition, policy), items in sorted(groups.items()):
        values = [float(item["second_flow_mbps"]) for item in items]
        avoid = [int(item["avoided_bottleneck"]) for item in items]
        loss = [float(item["connectivity_loss_pct"]) for item in items]
        n = len(values)
        mean = statistics.mean(values)
        sd = statistics.stdev(values) if n > 1 else 0.0
        margin = 1.96 * sd / math.sqrt(n) if n > 1 else 0.0
        result.append({
            "condition": condition,
            "telemetry_delay_seconds": CONDITIONS[condition][0],
            "telemetry_noise_std": CONDITIONS[condition][1],
            "policy": policy,
            "trials": n,
            "mean_second_flow_mbps": round(mean, 4),
            "std_second_flow_mbps": round(sd, 4),
            "min_second_flow_mbps": round(min(values), 4),
            "max_second_flow_mbps": round(max(values), 4),
            "approx_ci95_low_mbps": round(max(0.0, mean - margin), 4),
            "approx_ci95_high_mbps": round(mean + margin, 4),
            "bottleneck_avoidance_rate": round(statistics.mean(avoid), 4),
            "mean_connectivity_loss_pct": round(statistics.mean(loss), 4),
        })
    return result


def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_report(path, summaries, trials):
    lines = [
        "# Controlled Telemetry-Impairment Mininet Results",
        "",
        f"- Trials per policy per condition: {trials}",
        f"- Policies: {', '.join(POLICIES)}",
        f"- Conditions: {len(CONDITIONS)}",
        f"- Total Mininet trials: {trials * len(POLICIES) * len(CONDITIONS)}",
        "- Metric: second-flow TCP goodput (Mbps)",
        "- Confidence intervals: approximate normal 95% intervals",
        "",
        "| Condition | Delay (s) | Noise std | Policy | n | Mean Mbps | SD | Avoidance | Connectivity loss |",
        "|---|---:|---:|---|---:|---:|---:|---:|---:|",
    ]
    for row in summaries:
        lines.append(
            f"| {row['condition']} | {row['telemetry_delay_seconds']:.1f} "
            f"| {row['telemetry_noise_std']:.2f} | {row['policy']} "
            f"| {row['trials']} | {row['mean_second_flow_mbps']:.2f} "
            f"| {row['std_second_flow_mbps']:.2f} "
            f"| {row['bottleneck_avoidance_rate']:.0%} "
            f"| {row['mean_connectivity_loss_pct']:.2f}% |"
        )
    lines.extend([
        "",
        "## Interpretation notes",
        "",
        "- Compare policies within the same condition; compare conditions to assess impairment sensitivity.",
        "- A trial is valid only if the runner completes its connectivity check and records both flow decisions and goodput.",
        "- The avoidance rate is the fraction of second flows assigned to a path other than the bottlenecked first-flow path.",
        "- These are Mininet emulation results, not production-network measurements.",
        "- The experiment measures TCP goodput and path choice; it does not measure p99 latency, fairness, or controller CPU.",
        "- Noise standard deviation is applied to normalized utilization; 0.05 corresponds to five percentage points before clipping.",
        "- Delayed samples are historical telemetry samples, not merely an altered age label.",
        "- The 4-second/0.10 severe condition is a stress case and may cause fallback behavior; report failures rather than silently omitting them.",
        "",
        "Raw per-condition CSV files and the combined raw CSV are stored alongside this report.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=10,
                        help="trials per policy per condition (default: 10)")
    parser.add_argument("--conditions", nargs="+", choices=tuple(CONDITIONS),
                        default=list(CONDITIONS))
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--output-dir", type=Path,
                        default=Path("results/telemetry_matrix"))
    parser.add_argument("--venv", default=".venv")
    parser.add_argument("--controller-ip", default="127.0.0.1")
    parser.add_argument("--controller-port", type=int, default=6653)
    parser.add_argument("--bottleneck-rate", default="10mbit")
    parser.add_argument("--first-flow-seconds", type=int, default=30)
    parser.add_argument("--second-flow-seconds", type=int, default=8)
    parser.add_argument("--warmup-seconds", type=float, default=None,
                        help="default: max(6, delay + 4) for each condition")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the planned commands without starting Mininet")
    args = parser.parse_args()

    if args.trials < 1:
        parser.error("--trials must be positive")
    if not args.conditions:
        parser.error("select at least one condition")

    repo = Path.cwd().resolve()
    runner = repo / "experiments" / "mininet_policy_eval.py"
    if not runner.is_file():
        parser.error(f"run from repository root; missing {runner}")

    all_rows = []
    for condition in args.conditions:
        delay, noise = CONDITIONS[condition]
        warmup = args.warmup_seconds
        if warmup is None:
            warmup = max(6.0, delay + 4.0)
        if warmup < max(4.0, delay + 4.0):
            parser.error(
                f"{condition}: warm-up must be at least {max(4.0, delay + 4.0)} seconds"
            )
        if args.first_flow_seconds <= warmup + args.second_flow_seconds:
            parser.error(
                f"{condition}: first-flow duration must exceed warm-up + second-flow duration"
            )

        raw_path = args.output_dir / f"{condition}_raw.csv"
        command = [
            sys.executable, str(runner),
            "--policies", *POLICIES,
            "--trials", str(args.trials),
            "--telemetry-delay-seconds", str(delay),
            "--telemetry-noise-std", str(noise),
            "--seed", str(args.seed),
            "--warmup-seconds", str(warmup),
            "--first-flow-seconds", str(args.first_flow_seconds),
            "--second-flow-seconds", str(args.second_flow_seconds),
            "--bottleneck-rate", args.bottleneck_rate,
            "--controller-ip", args.controller_ip,
            "--controller-port", str(args.controller_port),
            "--venv", args.venv,
            "--output", str(raw_path),
        ]
        print(f"\n### {condition}: delay={delay}s noise_std={noise}", flush=True)
        print(" ".join(command), flush=True)
        if args.dry_run:
            continue

        subprocess.run(command, cwd=repo, check=True)
        with raw_path.open(newline="") as handle:
            condition_rows = list(csv.DictReader(handle))
        if len(condition_rows) != len(POLICIES) * args.trials:
            raise RuntimeError(
                f"{condition}: expected {len(POLICIES) * args.trials} rows, "
                f"found {len(condition_rows)} in {raw_path}"
            )
        for row in condition_rows:
            row["condition"] = condition
        all_rows.extend(condition_rows)
        # Persist the aggregate after every completed condition.
        write_csv(args.output_dir / "all_conditions_raw.csv", all_rows, RAW_FIELDS)
        summary = summarize(all_rows)
        write_csv(args.output_dir / "summary.csv", summary, list(summary[0]))
        write_report(args.output_dir / "REPORT.md", summary, args.trials)
        print(f"Completed {condition}; aggregate rows saved.", flush=True)

    if args.dry_run:
        print("\nDry run complete; no controller or Mininet processes were started.")
    else:
        print(f"\nAll selected conditions completed. Results: {args.output_dir}")


if __name__ == "__main__":
    main()
