"""Condition-stratified analysis for completed PathPilot final campaigns."""
from __future__ import annotations
import argparse
import csv
import json
import statistics
from pathlib import Path

from experiments.final_campaign import POLICIES
from experiments.final_metrics import bootstrap_mean_ci
from experiments.plot_final_campaign import plot_summary
from experiments.run_final_campaign import trial_directory
from experiments.audit_final_campaign import audit


def load_trial(root, row):
    path = trial_directory(root, row) / "trial_result.json"
    result = json.loads(path.read_text(encoding="utf-8"))
    traffic = result["traffic"]
    flows = traffic["flow_results"]
    event_path = Path(result["controller_event_log"])
    events = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()
              if line.strip()]
    qdisc_samples = [event for event in events if event.get("event") == "qdisc_sample"]
    ovs_samples = [event for event in events if event.get("event") == "ovs_port_sample"]
    qdisc_drop_values = [
        int(event["counters"]["qdisc_drops"]) for event in qdisc_samples
        if event.get("counters", {}).get("qdisc_drops") not in ("", None)
    ]
    qdisc_backlog_values = [
        int(event["counters"]["qdisc_backlog_bytes"]) for event in qdisc_samples
        if event.get("counters", {}).get("qdisc_backlog_bytes") not in ("", None)
    ]
    ovs_drop_values = [
        int(port.get("rx_dropped", 0)) + int(port.get("tx_dropped", 0))
        for event in ovs_samples for port in event.get("counters", [])
        if port.get("rx_dropped") not in ("", None)
        and port.get("tx_dropped") not in ("", None)
    ]
    goodputs = [float(flow["goodput_mbps"]) for flow in flows]
    udp_losses = [float(flow["udp_loss_pct"]) for flow in flows
                  if flow.get("protocol") == "UDP" and flow.get("udp_loss_pct") not in ("", None)]
    fairness = [float(value) for value in traffic["jain_fairness_by_second"].values()]
    adaptation = [
        float(item["utilization_settling_time_s"])
        for item in result.get("adaptation", [])
        if item.get("utilization_settling_time_s") not in ("", None)
    ]
    return {
        "scenario": row["scenario"],
        "condition": row["telemetry_condition"],
        "initial_path": row["initial_bottleneck_path"],
        "policy": row["policy"],
        "repetition": int(row["repetition"]),
        "seed": int(row["workload_seed"]),
        "tcp_app_rtt_p99_ms": float(traffic["tcp_application_rtt"]["tcp_app_rtt_ms_p99"]),
        "aggregate_goodput_mbps": sum(goodputs),
        "udp_loss_pct": statistics.mean(udp_losses) if udp_losses else "",
        "jain_fairness": statistics.mean(fairness) if fairness else "",
        "path_changes_per_minute": float(result["event_metrics"]["path_changes_per_minute"])
            if result["event_metrics"]["path_changes_per_minute"] not in ("", None) else "",
        "path_reversals": int(result["event_metrics"]["path_reversals"]),
        "qdisc_drops_counter_peak": max(qdisc_drop_values) if qdisc_drop_values else "",
        "qdisc_backlog_bytes_peak": max(qdisc_backlog_values) if qdisc_backlog_values else "",
        "ovs_port_drops_counter_peak": max(ovs_drop_values) if ovs_drop_values else "",
        "flow_mod_count": int(result["event_metrics"]["flow_mod_count"]),
        "telemetry_estimated_bytes": int(result["event_metrics"]["telemetry_estimated_bytes"]),
        "controller_cpu_seconds": float(result["controller_metrics"]["controller_cpu_seconds"])
            if result["controller_metrics"]["controller_cpu_seconds"] not in ("", None) else "",
        "controller_rss_peak_mb": float(result["controller_metrics"]["controller_rss_peak_mb"])
            if result["controller_metrics"]["controller_rss_peak_mb"] not in ("", None) else "",
        "utilization_settling_time_s": statistics.mean(adaptation) if adaptation else "",
    }


def _write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def analyze(manifest_path, output_root):
    manifest_path = Path(manifest_path)
    root = Path(output_root)
    audit(manifest_path, root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = [load_trial(root, row) for row in manifest["trials"]]
    metrics = (
        "tcp_app_rtt_p99_ms", "aggregate_goodput_mbps", "udp_loss_pct",
        "jain_fairness", "path_changes_per_minute", "path_reversals",
        "flow_mod_count", "telemetry_estimated_bytes", "qdisc_drops_counter_peak",
        "qdisc_backlog_bytes_peak", "ovs_port_drops_counter_peak", "controller_cpu_seconds",
        "controller_rss_peak_mb", "utilization_settling_time_s",
    )
    groups = {}
    for row in rows:
        groups.setdefault((row["scenario"], row["condition"], row["initial_path"],
                           row["policy"]), []).append(row)
    summary = []
    for (scenario, condition, initial, policy), items in sorted(groups.items()):
        out = {"scenario": scenario, "condition": condition,
               "initial_path": initial, "policy": policy, "trials": len(items)}
        for metric in metrics:
            values = [item[metric] for item in items if item[metric] not in ("", None)]
            ci = bootstrap_mean_ci(values, seed=manifest["seed_base"])
            out[f"{metric}_mean"] = ci["mean"]
            out[f"{metric}_ci95_low"] = ci["ci_low"]
            out[f"{metric}_ci95_high"] = ci["ci_high"]
            out[f"{metric}_n"] = ci["n"]
        summary.append(out)

    by_key = {
        (row["scenario"], row["condition"], row["initial_path"],
         row["repetition"], row["policy"]): row for row in rows
    }
    paired = []
    for scenario in manifest["scenarios"]:
        for condition in manifest["telemetry_conditions"]:
            for initial in manifest["initial_paths"]:
                keys = sorted({
                    (scenario, condition, initial, row["repetition"])
                    for row in rows if row["scenario"] == scenario
                    and row["condition"] == condition and row["initial_path"] == initial
                })
                for comparator in ("least_loaded", "threshold", "stability_aware"):
                    diffs = {name: [] for name in (
                        "p99_improvement_pct", "goodput_regression_pct",
                        "udp_loss_delta_pp", "jain_fairness_delta",
                        "path_changes_reduction_pct",
                    )}
                    for key in keys:
                        left = by_key.get((*key, comparator))
                        proposed = by_key.get((*key, "uncertainty_aware"))
                        if not left or not proposed:
                            continue
                        def pct_improvement(base, candidate):
                            return (100 * (base - candidate) / base) if base > 0 else ""
                        diffs["p99_improvement_pct"].append(
                            pct_improvement(left["tcp_app_rtt_p99_ms"],
                                            proposed["tcp_app_rtt_p99_ms"])
                        )
                        diffs["goodput_regression_pct"].append(
                            pct_improvement(left["aggregate_goodput_mbps"],
                                            proposed["aggregate_goodput_mbps"])
                        )
                        if left["udp_loss_pct"] != "" and proposed["udp_loss_pct"] != "":
                            diffs["udp_loss_delta_pp"].append(
                                proposed["udp_loss_pct"] - left["udp_loss_pct"]
                            )
                        if left["jain_fairness"] != "" and proposed["jain_fairness"] != "":
                            diffs["jain_fairness_delta"].append(
                                proposed["jain_fairness"] - left["jain_fairness"]
                            )
                        diffs["path_changes_reduction_pct"].append(
                            pct_improvement(left["path_changes_per_minute"],
                                            proposed["path_changes_per_minute"])
                            if left["path_changes_per_minute"] not in ("", None)
                            and proposed["path_changes_per_minute"] not in ("", None)
                            else ""
                        )
                    out = {"scenario": scenario, "condition": condition,
                           "initial_path": initial, "comparator": comparator}
                    for name, values in diffs.items():
                        values = [value for value in values if value != ""]
                        ci = bootstrap_mean_ci(values, seed=manifest["seed_base"])
                        out[f"{name}_mean"] = ci["mean"]
                        out[f"{name}_ci95_low"] = ci["ci_low"]
                        out[f"{name}_ci95_high"] = ci["ci_high"]
                        out[f"{name}_n"] = ci["n"]
                    paired.append(out)

    _write_csv(root / "FINAL_CAMPAIGN_SUMMARY.csv", summary)
    _write_csv(root / "PAIRED_POLICY_COMPARISONS.csv", paired)
    plots = plot_summary(root / "FINAL_CAMPAIGN_SUMMARY.csv", root / "plots")
    report = [
        "# PathPilot Final Campaign Analysis", "",
        f"- Trials analyzed: {len(rows)}",
        f"- Source revision: {manifest.get('git_revision')}",
        f"- Policies: {', '.join(manifest['policies'])}",
        f"- Scenarios: {', '.join(manifest['scenarios'])}",
        f"- Telemetry conditions: {', '.join(manifest['telemetry_conditions'])}",
        "",
        f"Generated {len(plots)} condition-stratified SVG plots in plots/.",
        "The CSV files report condition- and initial-path-stratified metrics with trial-level bootstrap 95% intervals. "
        "Paired comparisons use matched scenario/condition/path/repetition blocks.",
        "",
        "TCP application RTT is measured by the dedicated TCP echo probe under concurrent workload. "
        "UDP packet loss is reported only for UDP flows. Jain fairness is calculated only for time windows with "
        "at least two competing flows. Controller CPU/RSS are Ryu-process-only. Telemetry byte totals include "
        "estimated reply sizes when serialized buffers are unavailable.",
        "",
        "Do not pool workload families or telemetry conditions into one headline value. Evaluate the preregistered "
        "thresholds in the campaign manifest and report failures or mixed outcomes without post-hoc threshold changes.",
    ]
    (root / "FINAL_CAMPAIGN_ANALYSIS.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return {"trials": len(rows), "summary_rows": len(summary),
            "paired_rows": len(paired), "plots": len(plots)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.manifest, args.output_root)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
