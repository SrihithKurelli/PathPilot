import pytest

from experiments.analyze_mininet_results import summarize_mininet
from experiments.mininet_policy_eval import parse_iperf_mbps, parse_ping_metrics


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("[  1] 0.0-8.0 sec  80.0 MBytes  84.0 Mbits/sec", 84.0),
        ("[  1] 0.0-8.0 sec  800 KBytes  819.2 Kbits/sec", 0.8192),
        ("[  1] 0.0-8.0 sec  1.0 GBytes  1.05 Gbits/sec", 1050.0),
    ],
)
def test_parse_iperf_mbps(output, expected):
    assert parse_iperf_mbps(output) == pytest.approx(expected)


def test_parse_iperf_rejects_missing_bandwidth():
    with pytest.raises(ValueError, match="Could not parse"):
        parse_iperf_mbps("iperf failed")


def test_mininet_summary_groups_trials_and_reports_avoidance():
    rows = [
        {"policy": "least_loaded", "second_flow_mbps": "80",
         "avoided_bottleneck": "1"},
        {"policy": "least_loaded", "second_flow_mbps": "100",
         "avoided_bottleneck": "1"},
        {"policy": "static", "second_flow_mbps": "8",
         "avoided_bottleneck": "0"},
    ]
    result = summarize_mininet(rows)
    assert len(result) == 2
    least_loaded = next(row for row in result if row["policy"] == "least_loaded")
    static = next(row for row in result if row["policy"] == "static")
    assert least_loaded["trials"] == 2
    assert least_loaded["mean_second_flow_mbps"] == 90.0
    assert least_loaded["bottleneck_avoidance_rate"] == 1.0
    assert static["bottleneck_avoidance_rate"] == 0.0


def test_parse_ping_metrics_reports_percentiles_and_packet_loss():
    output = """10 packets transmitted, 9 received, 10% packet loss, time 9000ms
rtt min/avg/max/mdev = 1.000/2.000/9.000/2.000 ms
64 bytes from 10.0.0.2: icmp_seq=1 ttl=64 time=1.000 ms
64 bytes from 10.0.0.2: icmp_seq=2 ttl=64 time=2.000 ms
64 bytes from 10.0.0.2: icmp_seq=3 ttl=64 time=9.000 ms
"""
    result = parse_ping_metrics(output)
    assert result["icmp_probe_packets"] == 10
    assert result["icmp_probe_packet_loss_pct"] == 10.0
    assert result["icmp_probe_rtt_samples"] == 3
    assert result["icmp_probe_rtt_p50_ms"] == 2.0
    assert result["icmp_probe_rtt_p99_ms"] == 8.86


def test_parse_ping_metrics_rejects_missing_packet_loss():
    with pytest.raises(ValueError, match="Could not parse packet loss"):
        parse_ping_metrics("ping output without summary")



def test_repository_revision_records_tracked_and_untracked_changes(tmp_path):
    import subprocess

    from experiments.mininet_policy_eval import repository_revision

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "pathpilot-test@example.com"],
                   cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "PathPilot Test"],
                   cwd=tmp_path, check=True)
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("initial")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=tmp_path, check=True)

    revision, dirty = repository_revision(tmp_path)
    assert len(revision) == 40
    assert dirty == 0

    (tmp_path / "untracked.txt").write_text("new")
    _, dirty = repository_revision(tmp_path)
    assert dirty == 1

def test_mininet_summary_includes_successive_flow_metrics():
    import json

    rows = [
        {
            "policy": "uncertainty_aware",
            "second_flow_mbps": "80",
            "avoided_bottleneck": "1",
            "fallback_flow_avoidance_rate": "0.5",
            "fallback_flow_goodputs_mbps": json.dumps([80.0, 1.2]),
        },
        {
            "policy": "uncertainty_aware",
            "second_flow_mbps": "1.2",
            "avoided_bottleneck": "0",
            "fallback_flow_avoidance_rate": "1.0",
            "fallback_flow_goodputs_mbps": json.dumps([85.0, 85.0]),
        },
    ]
    result = summarize_mininet(rows)[0]
    assert result["successive_flow_avoidance_rate"] == 0.75
    assert result["successive_flow_mean_goodput_mbps"] == pytest.approx(62.8)



def test_mininet_summary_separates_first_and_successive_flow_metrics_by_condition():
    import json

    rows = [
        {
            "policy": "uncertainty_aware",
            "requested_initial_path": "s1-s2-s4",
            "telemetry_delay_seconds": "4.0",
            "telemetry_noise_std": "0.1",
            "bottleneck_rate": "10mbit",
            "bottleneck_path": "s1-s2-s4",
            "second_flow_mbps": "1.2",
            "avoided_bottleneck": "0",
            "fallback_flow_paths": json.dumps(["s1-s2-s4", "s1-s3-s4", "s1-s2-s4", "s1-s3-s4"]),
            "fallback_flow_goodputs_mbps": json.dumps([1.2, 85.0, 0.5, 85.0]),
            "fallback_flow_client_returncodes": json.dumps([0, 0, 0, 0]),
        },
        {
            "policy": "uncertainty_aware",
            "requested_initial_path": "s1-s3-s4",
            "telemetry_delay_seconds": "4.0",
            "telemetry_noise_std": "0.1",
            "bottleneck_rate": "10mbit",
            "bottleneck_path": "s1-s3-s4",
            "second_flow_mbps": "85.0",
            "avoided_bottleneck": "1",
            "fallback_flow_paths": json.dumps(["s1-s2-s4", "s1-s3-s4", "s1-s2-s4", "s1-s3-s4"]),
            "fallback_flow_goodputs_mbps": json.dumps([85.0, 2.0, 85.0, 2.0]),
            "fallback_flow_client_returncodes": json.dumps([0, 0, 0, 0]),
        },
    ]

    result = summarize_mininet(rows)
    assert len(result) == 2
    path1 = next(row for row in result if row["bottleneck_path"] == "s1-s2-s4")
    path2 = next(row for row in result if row["bottleneck_path"] == "s1-s3-s4")
    assert path1["first_policy_flow_avoidance_rate"] == 0.0
    assert path1["successive_flow_avoidance_rate"] == 0.5
    assert path2["first_policy_flow_avoidance_rate"] == 1.0
    assert path2["successive_flow_avoidance_rate"] == 0.5
    assert path1["successive_flow_count"] == 4
    assert path1["successive_flow_mean_goodput_mbps"] == 42.925


def test_mininet_summary_rejects_mismatched_successive_flow_arrays():
    import json

    row = {
        "policy": "uncertainty_aware",
        "requested_initial_path": "s1-s2-s4",
        "bottleneck_path": "s1-s2-s4",
        "second_flow_mbps": "1.0",
        "avoided_bottleneck": "0",
        "fallback_flow_paths": json.dumps(["s1-s2-s4", "s1-s3-s4"]),
        "fallback_flow_goodputs_mbps": json.dumps([1.0]),
    }
    with pytest.raises(ValueError, match="lengths differ"):
        summarize_mininet([row])
