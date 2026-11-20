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


def _decode_array(row, field):
    value = row.get(field, "")
    if value in ("", None):
        return []
    decoded = json.loads(value) if isinstance(value, str) else value
    if not isinstance(decoded, list):
        raise ValueError(f"{field} must contain a JSON array")
    return decoded


def _mean(values):
    return statistics.mean(values) if values else 0.0


def _sd(values):
    return statistics.stdev(values) if len(values) > 1 else 0.0


def summarize_mininet(rows):
    """Summarize separately by policy, pinned bottleneck path, and telemetry condition."""
    groups = defaultdict(list)
    for row in rows:
        key = (
            row.get("policy", "unknown"),
            row.get("requested_initial_path", "unspecified"),
            row.get("telemetry_delay_seconds", "unspecified"),
            row.get("telemetry_noise_std", "unspecified"),
            row.get("bottleneck_rate", "unspecified"),
        )
        groups[key].append(row)

    summaries = []
    for key, items in sorted(groups.items()):
        policy, initial_path, delay, noise, bottleneck_rate = key
        first_goodputs = [float(item["second_flow_mbps"]) for item in items]
        first_avoided = [int(item["avoided_bottleneck"]) for item in items]
        per_trial_flow_goodputs = []
        per_trial_flow_avoidance = []
        total_successive_flows = 0
        all_flow_goodputs = []
        all_flow_avoided = []

        for item in items:
            flow_goodputs = [float(v) for v in _decode_array(item, "fallback_flow_goodputs_mbps")]
            flow_paths = _decode_array(item, "fallback_flow_paths")
            returncodes = _decode_array(item, "fallback_flow_client_returncodes")
            bottleneck_path = item.get("bottleneck_path") or item.get("first_flow_path")

            if flow_paths and len(flow_paths) != len(flow_goodputs):
                raise ValueError("fallback_flow_paths and fallback_flow_goodputs_mbps lengths differ")
            if returncodes and len(returncodes) != len(flow_goodputs):
                raise ValueError("fallback_flow_client_returncodes and goodput lengths differ")
            if returncodes and any(int(code) != 0 for code in returncodes):
                raise ValueError("Cannot summarize a trial with failed successive-flow clients")

            if flow_goodputs:
                avoided = [int(path != bottleneck_path) for path in flow_paths]
                if not flow_paths:
                    # Legacy datasets may have goodputs but no recorded path sequence.
                    avoided = []
                per_trial_flow_goodputs.append(_mean(flow_goodputs))
                if avoided:
                    per_trial_flow_avoidance.append(_mean(avoided))
                    all_flow_avoided.extend(avoided)
                elif item.get("fallback_flow_avoidance_rate") not in ("", None):
                    # Older pilot CSVs recorded the per-trial rate but not paths.
                    per_trial_flow_avoidance.append(
                        float(item["fallback_flow_avoidance_rate"])
                    )
                all_flow_goodputs.extend(flow_goodputs)
                total_successive_flows += len(flow_goodputs)

        n = len(first_goodputs)
        mean = _mean(first_goodputs)
        sd = _sd(first_goodputs)
        margin = 1.96 * sd / math.sqrt(n) if n > 1 else 0.0
        summary = {
            "policy": policy,
            "bottleneck_path": initial_path,
            "telemetry_delay_seconds": delay,
            "telemetry_noise_std": noise,
            "bottleneck_rate": bottleneck_rate,
            "trials": n,
            "mean_first_policy_flow_goodput_mbps": round(mean, 4),
            "mean_second_flow_mbps": round(mean, 4),  # backward-compatible alias
            "std_first_policy_flow_goodput_mbps": round(sd, 4),
            "approx_ci95_low_first_flow_mbps": round(max(0.0, mean - margin), 4),
            "approx_ci95_high_first_flow_mbps": round(mean + margin, 4),
            "first_policy_flow_avoidance_rate": round(_mean(first_avoided), 4),
            "bottleneck_avoidance_rate": round(_mean(first_avoided), 4),  # legacy alias
            "successive_flow_trials": len(per_trial_flow_goodputs),
            "successive_flow_count": total_successive_flows,
            "successive_flow_avoidance_rate": (
                round(_mean(per_trial_flow_avoidance), 4) if per_trial_flow_avoidance else ""
            ),
            "successive_flow_mean_goodput_mbps": (
                round(_mean(all_flow_goodputs), 4) if all_flow_goodputs else ""
            ),
            "mean_per_trial_successive_goodput_mbps": (
                round(_mean(per_trial_flow_goodputs), 4) if per_trial_flow_goodputs else ""
            ),
        }
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
        raise SystemExit("Input must contain columns: " + ", ".join(sorted(required)))

    summary = summarize_mininet(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)

    print(f"Wrote {len(summary)} condition-specific policy summaries to {args.output}")
    print("95% intervals are normal-approximation intervals, not exact small-sample intervals.")
    for row in summary:
        print(
            f"{row['policy']:18} bottleneck={row['bottleneck_path']:16} "
            f"delay={row['telemetry_delay_seconds']}s noise={row['telemetry_noise_std']} "
            f"n={row['trials']} first-flow={row['mean_first_policy_flow_goodput_mbps']:.2f} Mbps "
            f"first-avoid={row['first_policy_flow_avoidance_rate']:.0%} "
            f"successive-avoid={row['successive_flow_avoidance_rate']}"
        )


if __name__ == "__main__":
    main()
