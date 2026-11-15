#!/usr/bin/env python3
"""Summarize policy replay or experiment CSV results by scenario and policy."""
from __future__ import annotations

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path


def percentile(values, fraction):
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row["scenario"], row["policy"])].append(row)
    output = []
    for (scenario, policy), items in sorted(groups.items()):
        regret = [float(x["regret"]) for x in items]
        true_util = [float(x["selected_true_utilization"]) for x in items]
        oracle = [float(x["oracle_choice"]) for x in items]
        confidence = [float(x["selected_confidence"]) for x in items
                      if x.get("selected_confidence") not in (None, "")]
        output.append({
            "scenario": scenario,
            "policy": policy,
            "decisions": len(items),
            "mean_selected_true_utilization": round(statistics.mean(true_util), 6),
            "mean_regret": round(statistics.mean(regret), 6),
            "p95_regret": round(percentile(regret, 0.95), 6),
            "oracle_choice_rate": round(statistics.mean(oracle), 6),
            "mean_selected_confidence": round(statistics.mean(confidence), 6)
                if confidence else "",
        })
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, nargs="?",
                        default=Path("results/policy_replay.csv"))
    parser.add_argument("--output", type=Path,
                        default=Path("results/policy_summary.csv"))
    args = parser.parse_args()
    with args.input.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {"scenario", "policy", "regret",
                "selected_true_utilization", "oracle_choice"}
    if not rows or not required.issubset(rows[0]):
        raise SystemExit(f"Input must contain columns: {', '.join(sorted(required))}")
    summary = summarize(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    print(f"Wrote {len(summary)} scenario/policy summaries to {args.output}")
    for row in summary:
        print(
            f'{row["scenario"]:16} {row["policy"]:18} '
            f'mean regret={row["mean_regret"]:.4f} '
            f'oracle rate={row["oracle_choice_rate"]:.1%}'
        )


if __name__ == "__main__":
    main()
