"""Strict integrity audit for completed PathPilot final-campaign artifacts."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from experiments.final_campaign import build_manifest
from experiments.run_final_campaign import trial_directory
from experiments.scenarios import scenario_digest


def audit(manifest_path, output_root):
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    rows = manifest.get("trials", [])
    if not rows:
        raise ValueError("manifest contains no trials")
    keys = set()
    failures = []
    audited = []
    for row in rows:
        key = (row["scenario"], row["telemetry_condition"],
               row["initial_bottleneck_path"], row["policy"],
               int(row["repetition"]))
        if key in keys:
            failures.append(f"duplicate manifest key: {key}")
            continue
        keys.add(key)
        folder = trial_directory(Path(output_root), row)
        result_path = folder / "trial_result.json"
        event_path = folder / "controller_events.jsonl"
        if not result_path.is_file() or not event_path.is_file():
            failures.append(f"missing result or event log: {folder}")
            continue
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
            events = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()
                      if line.strip()]
        except Exception as exc:
            failures.append(f"invalid JSON artifact in {folder}: {exc}")
            continue

        expected = (
            row["policy"], row["scenario"], row["telemetry_condition"],
            row["initial_bottleneck_path"], int(row["repetition"]),
            int(row["workload_seed"]), row["scenario_sha256"],
        )
        actual_condition = (
            "baseline" if result.get("telemetry_delay_seconds") == 0
                and result.get("telemetry_noise_std") == 0 else
            "delayed" if result.get("telemetry_delay_seconds") > 0
                and result.get("telemetry_noise_std") == 0 else
            "noisy" if result.get("telemetry_delay_seconds") == 0 else "combined"
        )
        actual = (
            result.get("policy"), result.get("scenario"), actual_condition,
            result.get("initial_bottleneck_path"), int(result.get("repetition", -1)),
            int(result.get("seed", -1)), result.get("scenario_sha256"),
        )
        if actual != expected:
            failures.append(f"manifest/result mismatch: {folder}")
            continue
        if result.get("git_revision") != manifest.get("git_revision"):
            failures.append(f"trial source revision differs from manifest: {folder}")
        if result.get("working_tree_dirty") != 0:
            failures.append(f"trial working tree was dirty: {folder}")

        traffic = result.get("traffic", {})
        flows = traffic.get("flow_results", [])
        if not flows:
            failures.append(f"no traffic flow results: {folder}")
        if any(flow.get("client_returncode") != 0 for flow in flows):
            failures.append(f"failed iperf3 client: {folder}")
        if any(flow.get("goodput_mbps") in ("", None)
               or flow.get("bytes_received") in ("", None) for flow in flows):
            failures.append(f"missing per-flow goodput/delivered-byte evidence: {folder}")
        for flow in flows:
            if flow.get("protocol") == "TCP":
                if flow.get("receiver_goodput_mbps") in ("", None) or flow.get("sender_goodput_mbps") in ("", None):
                    failures.append(f"missing separate TCP sender/receiver rate evidence: {folder}")
                if flow.get("receiver_duration_s") in ("", None) or float(flow.get("receiver_duration_s", 0)) <= 0:
                    failures.append(f"missing positive TCP receiver duration: {folder}")
                if flow.get("receiver_report_source") not in {"server", "client"}:
                    failures.append(f"missing TCP receiver report provenance: {folder}")
        if any(flow.get("protocol") == "TCP" and flow.get("tcp_retransmits") in ("", None)
               for flow in flows):
            failures.append(f"missing TCP retransmission evidence: {folder}")
        if any(flow.get("protocol") == "UDP" and flow.get("udp_loss_pct") in ("", None)
               for flow in flows):
            failures.append(f"missing UDP packet-loss evidence: {folder}")
        rtt = traffic.get("tcp_application_rtt", {})
        if not rtt.get("tcp_app_rtt_ms_count") or rtt.get("tcp_app_rtt_ms_p99") in ("", None):
            failures.append(f"missing TCP application RTT p99: {folder}")
        fairness = traffic.get("jain_fairness_by_second", {})
        if len(flows) > 1 and not fairness:
            failures.append(f"no concurrent-flow fairness windows: {folder}")
        metrics = result.get("event_metrics", {})
        for field in ("path_decisions", "flow_mod_count", "telemetry_request_count",
                      "telemetry_reply_count", "telemetry_estimated_bytes",
                      "telemetry_samples"):
            if field not in metrics:
                failures.append(f"missing event metric {field}: {folder}")
        if metrics.get("telemetry_request_count", 0) <= 0 or metrics.get("telemetry_reply_count", 0) <= 0:
            failures.append(f"missing OpenFlow telemetry messages: {folder}")
        if result.get("connectivity_loss_pct") != 0:
            failures.append(f"topology connectivity loss: {folder}")
        link_outages = result.get("link_outages", [])
        if row["scenario"] == "link_loss_recovery" and not link_outages:
            failures.append(f"missing link outage/recovery evidence: {folder}")
        for outage in link_outages:
            down_time = outage.get("down_monotonic_time")
            up_time = outage.get("up_monotonic_time")
            if down_time in ("", None) or up_time in ("", None):
                failures.append(f"incomplete link outage/recovery timestamps: {folder}")
            else:
                try:
                    if float(up_time) <= float(down_time):
                        failures.append(f"invalid link recovery timestamp order: {folder}")
                    duration = outage.get("scheduled_outage_duration_s")
                    if duration in ("", None) or float(duration) <= 0:
                        failures.append(f"missing positive link outage duration: {folder}")
                except (TypeError, ValueError):
                    failures.append(f"invalid link outage/recovery timestamp: {folder}")
        if result.get("network_sampler_errors"):
            failures.append(f"network counter sampler errors: {folder}")
        if traffic.get("impairment_errors"):
            failures.append(f"impairment execution errors: {folder}")
        controller_metrics = result.get("controller_metrics", {})
        if controller_metrics.get("controller_cpu_seconds") in ("", None):
            failures.append(f"missing controller CPU metric: {folder}")
        if controller_metrics.get("controller_rss_peak_mb") in ("", None):
            failures.append(f"missing controller RSS metric: {folder}")
        if metrics.get("flow_mod_count", 0) <= 0:
            failures.append(f"missing FlowMod count: {folder}")
        if not events:
            failures.append(f"empty controller event log: {folder}")
        event_types = {event.get("event") for event in events}
        qdisc_events = [event for event in events if event.get("event") == "qdisc_sample"]
        ovs_events = [event for event in events if event.get("event") == "ovs_port_sample"]
        if not qdisc_events or not any(
            sample.get("counters", {}).get("qdisc_drops") not in ("", None)
            and sample.get("counters", {}).get("qdisc_packets") not in ("", None)
            for sample in qdisc_events
        ):
            failures.append(f"missing qdisc packet/drop counters: {folder}")
        if not ovs_events or not any(
            port.get("rx_dropped") not in ("", None)
            and port.get("tx_dropped") not in ("", None)
            for event in ovs_events for port in event.get("counters", [])
        ):
            failures.append(f"missing OVS port drop counters: {folder}")
        if "flow_mod" not in event_types:
            failures.append(f"missing FlowMod evidence: {folder}")
        audited.append({
            "key": key,
            "flow_count": len(flows),
            "rtt_samples": rtt.get("tcp_app_rtt_ms_count", 0),
            "fairness_windows": len(fairness),
            "event_count": len(events),
            "path_decisions": metrics.get("path_decisions", 0),
        })

    expected_count = len(rows)
    if len(keys) != expected_count:
        failures.append("manifest trial keys are not unique")
    report = {
        "manifest_trial_count": expected_count,
        "audited_trial_count": len(audited),
        "failed_checks": failures,
        "passed": not failures and len(audited) == expected_count,
        "audit_rows": audited,
    }
    path = Path(output_root) / "FINAL_CAMPAIGN_AUDIT.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if failures:
        raise RuntimeError(f"final campaign audit failed ({len(failures)} findings); see {path}")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.manifest, args.output_root)
    print(f"PASS: audited {report['audited_trial_count']} final-campaign trials")


if __name__ == "__main__":
    main()
