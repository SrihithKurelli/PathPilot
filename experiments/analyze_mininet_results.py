#!/usr/bin/env python3
"""Summarize repeated Mininet policy-evaluation trials."""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


def summarize_mininet(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["policy"]].append(row)

    summaries = []
    for policy, items in sorted(groups.items()):
        goodput = [float(item["second_flow_mbps"]) for item in items]
        avoided = [int(item["avoided_bottleneck"]) for item in items]
        n = len(goodput)
        mean = statistics.mean(goodput)
        sd = statistics.stdev(goodput) if n > 1 else 0.0
        # Normal-approximation interval; label it explicitly as approximate.
        margin = 1.96 * sd / math.sqrt(n) if n > 1 else 0.0
        summary = {
            "policy": policy,
            "trials": n,
            "mean_second_flow_mbps": round(mean, 4),
            "std_second_flow_mbps": round(sd, 4),
            "min_second_flow_mbps": round(min(goodput), 4),
            "max_second_flow_mbps": round(max(goodput), 4),
            "approx_ci95_low_mbps": round(max(0.0, mean - margin), 4),
            "approx_ci95_high_mbps": round(mean + margin, 4),
            "bottleneck_avoidance_rate": round(statistics.mean(avoided), 4),
        }
        if all("fallback_flow_avoidance_rate" in item for item in items):
            summary["successive_flow_avoidance_rate"] = round(
                statistics.mean(float(item["fallback_flow_avoidance_rate"]) for item in items),
                4,
            )
            flow_goodputs = [
                float(value)
                for item in items
                for value in json.loads(item["fallback_flow_goodputs_mbps"])
            ]
            if flow_goodputs:
                summary["successive_flow_mean_goodput_mbps"] = round(
                    statistics.mean(flow_goodputs), 4
                )
        summaries.append(summary)
    return summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path,
                        default=Path("results/mininet_policy_results.csv"))
    parser.add_argument("--output", type=Path,
                        default=Path("results/mininet_policy_summary.csv"))
    args = parser.parse_args()

    with args.input.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {"policy", "second_flow_mbps", "avoided_bottleneck"}
    if not rows or not required.issubset(rows[0]):
        raise SystemExit(
            "Input must contain columns: " + ", ".join(sorted(required))
        )

    summary = summarize_mininet(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)

    print(f"Wrote {len(summary)} policy summaries to {args.output}")
    print("95% intervals are normal-approximation intervals, not exact small-sample intervals.")
    for row in summary:
        print(
            f"{row['policy']:18} n={row['trials']} "
            f"mean={row['mean_second_flow_mbps']:.2f} Mbps "
            f"sd={row['std_second_flow_mbps']:.2f} "
            f"avoidance={row['bottleneck_avoidance_rate']:.0%}"
        )


if __name__ == "__main__":
    main()
