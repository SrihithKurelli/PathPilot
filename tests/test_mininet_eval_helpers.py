import pytest

from experiments.analyze_mininet_results import summarize_mininet
from experiments.mininet_policy_eval import parse_iperf_mbps


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
