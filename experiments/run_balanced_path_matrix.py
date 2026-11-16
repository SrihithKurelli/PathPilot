#!/usr/bin/env python3
"""Run a counterbalanced Mininet matrix with both initial bottleneck paths.

For every telemetry condition, the first TCP flow is pinned equally to Path 1
and Path 2. The controller policy remains responsible for the second flow.
Each (condition, initial path) cell is saved independently so completed cells
can be resumed without losing earlier measurements.
"""
from __future__ import annotations

import argparse
import csv
import statistics
import subprocess
import sys
from pathlib import Path

POLICIES = ("static", "least_loaded", "threshold", "uncertainty_aware")
PATHS = {"path1": "s1-s2-s4", "path2": "s1-s3-s4"}
CONDITIONS = {
    "baseline": (0.0, 0.0),
    "delayed": (2.0, 0.0),
    "noisy": (0.0, 0.05),
    "combined": (2.0, 0.05),
    "severe_combined": (4.0, 0.10),
}
RAW_FIELDS = (
    "condition", "initial_path", "policy", "trial", "seed",
    "telemetry_delay_seconds", "telemetry_noise_std",
    "connectivity_loss_pct", "first_flow_path", "bottleneck_path",
    "bottleneck_interface", "bottleneck_rate", "second_flow_path",
    "avoided_bottleneck", "second_flow_mbps", "first_flow_mbps",
    "warmup_seconds", "first_selection_log", "second_selection_log",
    "first_telemetry_log", "second_telemetry_log",
)


def summarize(rows):
    groups = {}
    for row in rows:
        key = (row["condition"], row["initial_path"], row["policy"])
        groups.setdefault(key, []).append(row)

    summaries = []
    for (condition, initial_path, policy), items in sorted(groups.items()):
        values = sorted(float(item["second_flow_mbps"]) for item in items)
        avoidance = [int(item["avoided_bottleneck"]) for item in items]
        losses = [float(item["connectivity_loss_pct"]) for item in items]
        n = len(values)
        q1, _, q3 = statistics.quantiles(values, n=4, method="inclusive") if n > 1 else (
            values[0], values[0], values[0]
        )
        summaries.append({
            "condition": condition,
            "telemetry_delay_seconds": CONDITIONS[condition][0],
            "telemetry_noise_std": CONDITIONS[condition][1],
            "initial_path": initial_path,
            "policy": policy,
            "trials": n,
            "mean_second_flow_mbps": round(statistics.mean(values), 4),
            "median_second_flow_mbps": round(statistics.median(values), 4),
            "q1_second_flow_mbps": round(q1, 4),
            "q3_second_flow_mbps": round(q3, 4),
            "iqr_second_flow_mbps": round(q3 - q1, 4),
            "std_second_flow_mbps": round(statistics.stdev(values), 4) if n > 1 else 0.0,
            "min_second_flow_mbps": round(values[0], 4),
            "max_second_flow_mbps": round(values[-1], 4),
            "bottleneck_avoidance_rate": round(statistics.mean(avoidance), 4),
            "mean_connectivity_loss_pct": round(statistics.mean(losses), 4),
        })
    return summaries


def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def cell_file(output_dir, condition, path_key):
    return output_dir / f"{condition}_{path_key}_raw.csv"


def load_completed_cells(output_dir):
    rows = []
    for condition in CONDITIONS:
        for path_key, path_name in PATHS.items():
            raw_path = cell_file(output_dir, condition, path_key)
            if not raw_path.is_file():
                continue
            with raw_path.open(newline="") as handle:
                cell_rows = list(csv.DictReader(handle))
            counts = {policy: 0 for policy in POLICIES}
            for row in cell_rows:
                if row.get("policy") not in counts:
                    raise RuntimeError(f"{raw_path}: unexpected policy {row.get('policy')!r}")
                if row.get("first_flow_path") != path_name:
                    raise RuntimeError(
                        f"{raw_path}: expected pinned first path {path_name}, "
                        f"found {row.get('first_flow_path')}"
                    )
                counts[row["policy"]] += 1
                row["condition"] = condition
                row["initial_path"] = path_name
            if not cell_rows or len(set(counts.values())) != 1 or any(
                count == 0 for count in counts.values()
            ):
                raise RuntimeError(f"{raw_path}: unbalanced policy counts {counts}")
            rows.extend(cell_rows)
    return rows


def write_report(path, summaries):
    conditions = sorted({row["condition"] for row in summaries})
    total = sum(row["trials"] for row in summaries)
    lines = [
        "# Counterbalanced Initial-Path Mininet Results",
        "",
        f"- Conditions included: {len(conditions)} ({', '.join(conditions)})",
        f"- Initial bottleneck paths: {', '.join(PATHS.values())}",
        f"- Policies: {', '.join(POLICIES)}",
        f"- Total Mininet trials represented: {total}",
        "- Primary metric: second-flow TCP goodput (Mbps)",
        "- Dispersion: median and inclusive interquartile range (Q1–Q3)",
        "",
        "| Condition | Initial/bottleneck path | Policy | n | Mean Mbps | Median Mbps | Q1–Q3 Mbps | Avoidance |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in summaries:
        lines.append(
            f"| {row['condition']} | {row['initial_path']} | {row['policy']} "
            f"| {row['trials']} | {row['mean_second_flow_mbps']:.2f} "
            f"| {row['median_second_flow_mbps']:.2f} "
            f"| {row['q1_second_flow_mbps']:.2f}–{row['q3_second_flow_mbps']:.2f} "
            f"| {row['bottleneck_avoidance_rate']:.0%} |"
        )
    lines.extend([
        "",
        "## Interpretation and validity",
        "",
        "- Compare policies within the same condition and initial path before combining path placements.",
        "- The first flow is pinned by a test-only controller setting; it does not update the controller's previous-policy-path state.",
        "- The second flow is selected by the configured routing policy using the controller's telemetry and normal policy logic.",
        "- Avoidance means the second flow used a path other than the independently pinned, bottlenecked initial path.",
        "- Both initial paths are represented separately so path-order effects remain visible.",
        "- These are Mininet/OVS emulation results, not physical-network or production measurements.",
        "- The experiment measures TCP goodput and path choice; it does not measure p99 latency, fairness, or controller CPU.",
        "- The first pinned flow does not consume a telemetry sample or update the policy's previous-path state; first-flow telemetry fields explicitly record that pin.",
        "- All raw trial rows and controller log evidence are retained in the cell CSVs and combined CSV.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def rebuild(output_dir):
    rows = load_completed_cells(output_dir)
    if not rows:
        raise RuntimeError(f"No completed path-placement cells found in {output_dir}")
    write_csv(output_dir / "all_balanced_raw.csv", rows, RAW_FIELDS)
    summaries = summarize(rows)
    write_csv(output_dir / "balanced_summary.csv", summaries, list(summaries[0]))
    write_report(output_dir / "BALANCED_REPORT.md", summaries)
    return rows, summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=10,
                        help="trials per policy, condition, and initial path (default: 10)")
    parser.add_argument("--conditions", nargs="+", choices=tuple(CONDITIONS),
                        default=list(CONDITIONS))
    parser.add_argument("--initial-paths", nargs="+", choices=tuple(PATHS),
                        default=list(PATHS))
    parser.add_argument("--policies", nargs="+", choices=POLICIES, default=list(POLICIES))
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--output-dir", type=Path,
                        default=Path("results/balanced_telemetry_matrix"))
    parser.add_argument("--venv", default=".venv")
    parser.add_argument("--controller-ip", default="127.0.0.1")
    parser.add_argument("--controller-port", type=int, default=6653)
    parser.add_argument("--bottleneck-rate", default="10mbit")
    parser.add_argument("--first-flow-seconds", type=int, default=30)
    parser.add_argument("--second-flow-seconds", type=int, default=8)
    parser.add_argument("--warmup-seconds", type=float, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true",
                        help="skip cells already completed with the requested trial/policy counts")
    parser.add_argument("--aggregate-only", action="store_true")
    args = parser.parse_args()

    if args.trials < 1:
        parser.error("--trials must be positive")
    if not args.conditions or not args.initial_paths or not args.policies:
        parser.error("select at least one condition, initial path, and policy")

    repo = Path.cwd().resolve()
    runner = repo / "experiments" / "mininet_policy_eval.py"
    if not runner.is_file():
        parser.error(f"run from repository root; missing {runner}")

    if args.aggregate_only:
        rows, summaries = rebuild(args.output_dir)
        print(f"Rebuilt balanced aggregates from {len(rows)} trials.")
        return

    for condition in args.conditions:
        delay, noise = CONDITIONS[condition]
        warmup = args.warmup_seconds
        if warmup is None:
            warmup = max(6.0, delay + 4.0)
        if warmup < max(4.0, delay + 4.0):
            parser.error(f"{condition}: warm-up must be at least {max(4.0, delay + 4.0)} seconds")
        if args.first_flow_seconds <= warmup + args.second_flow_seconds:
            parser.error(f"{condition}: first-flow duration must exceed warm-up + second-flow duration")

        for path_key in args.initial_paths:
            initial_path = PATHS[path_key]
            output = cell_file(args.output_dir, condition, path_key)
            if output.exists():
                if not args.resume:
                    parser.error(f"{output} already exists; choose another output directory or use --resume")
                with output.open(newline="") as handle:
                    existing = list(csv.DictReader(handle))
                expected = len(args.policies) * args.trials
                counts = {policy: sum(row.get("policy") == policy for row in existing)
                          for policy in args.policies}
                if len(existing) != expected or any(count != args.trials for count in counts.values()):
                    parser.error(f"{output} exists but is not a complete matching cell: {counts}")
                if any(row.get("first_flow_path") != initial_path for row in existing):
                    parser.error(f"{output} contains rows for a different initial path")
                print(f"Skipping completed cell {condition}/{path_key}")
                continue

            command = [
                sys.executable, str(runner),
                "--policies", *args.policies,
                "--trials", str(args.trials),
                "--initial-path", initial_path,
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
                "--output", str(output),
            ]
            print(f"\n### {condition}, initial path={initial_path}", flush=True)
            print(" ".join(command), flush=True)
            if args.dry_run:
                continue

            subprocess.run(command, cwd=repo, check=True)
            with output.open(newline="") as handle:
                cell_rows = list(csv.DictReader(handle))
            expected = len(args.policies) * args.trials
            if len(cell_rows) != expected:
                raise RuntimeError(f"{output}: expected {expected} rows, found {len(cell_rows)}")
            if any(row["first_flow_path"] != initial_path for row in cell_rows):
                raise RuntimeError(f"{output}: controller did not honor initial path pin")
            # Rebuild after each completed cell so partial matrix progress is durable.
            rebuild(args.output_dir)

    if args.dry_run:
        print("\nDry run complete; no controller or Mininet processes were started.")
    else:
        rows, summaries = rebuild(args.output_dir)
        print(f"\nBalanced experiment matrix contains {len(rows)} trials.")
        print(f"Report: {args.output_dir / 'BALANCED_REPORT.md'}")


if __name__ == "__main__":
    main()
