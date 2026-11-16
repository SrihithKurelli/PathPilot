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
