import pytest

from experiments.final_metrics import (
    aggregate_concurrent_flow_fairness, bootstrap_mean_ci, jain_fairness,
    parse_iperf3_intervals, parse_iperf3_json, parse_ovs_port_stats, parse_ss_tcp_rtt,
    parse_tc_qdisc_stats, path_stability, percentile, settling_time,
    summarize_distribution,
)


def test_percentile_and_distribution_summary():
    assert percentile([0, 10], .5) == 5
    result = summarize_distribution([1, 2, 3], "latency_ms")
    assert result["latency_ms_p99"] == pytest.approx(2.98)
    assert result["latency_ms_count"] == 3


def test_jain_fairness_only_uses_concurrent_window():
    assert jain_fairness([10, 10]) == 1
    assert jain_fairness([10, 0]) == pytest.approx(.5)
    assert aggregate_concurrent_flow_fairness([
        {"window_id": "w1", "goodput_mbps": 10},
        {"window_id": "w1", "goodput_mbps": 10},
        {"window_id": "w2", "goodput_mbps": 10},
        {"window_id": "w2", "goodput_mbps": 0},
    ]) == {"w1": 1.0, "w2": .5}


def test_bootstrap_ci_is_deterministic():
    first = bootstrap_mean_ci([1, 2, 3, 4], resamples=500, seed=11)
    second = bootstrap_mean_ci([1, 2, 3, 4], resamples=500, seed=11)
    assert first == second
    assert first["n"] == 4


def test_path_stability_rate_and_reversal_window():
    result = path_stability([
        {"path": "A", "monotonic_time": 0},
        {"path": "B", "monotonic_time": 10},
        {"path": "A", "monotonic_time": 20},
        {"path": "A", "monotonic_time": 40},
    ], window_seconds=25)
    assert result["path_changes"] == 2
    assert result["path_reversals"] == 1
    assert result["path_changes_per_minute"] == pytest.approx(3)


def test_settling_time_requires_continuous_hold():
    samples = [
        {"monotonic_time": 11, "utilization": .2},
        {"monotonic_time": 13, "utilization": .8},
        {"monotonic_time": 14, "utilization": .2},
        {"monotonic_time": 17, "utilization": .2},
    ]
    assert settling_time([10], samples, .5, 2) == 4
    assert settling_time([10], samples[:2], .5, 2) == ""


def test_parse_iperf3_keeps_tcp_retransmits_distinct_from_udp_loss():
    tcp = parse_iperf3_json({
        "start": {"test_start": {"protocol": "TCP"}},
        "end": {"sum_received": {"bits_per_second": 2_000_000, "bytes": 1000},
                "sum_sent": {"retransmits": 7}},
    })
    assert tcp["goodput_mbps"] == 2
    assert tcp["tcp_retransmits"] == 7
    assert tcp["udp_loss_pct"] == ""

    udp = parse_iperf3_json({
        "start": {"test_start": {"protocol": "UDP"}},
        "end": {"sum": {"bits_per_second": 1_000_000, "bytes": 1000,
                        "packets": 100, "lost_packets": 5, "jitter_ms": 1.2}},
    })
    assert udp["udp_loss_pct"] == 5
    assert udp["udp_jitter_ms"] == 1.2
    assert udp["tcp_retransmits"] == ""



def test_udp_parser_prefers_server_receiver_and_intervals():
    import json

    client = {
        "start": {"test_start": {"protocol": "UDP"}},
        "end": {"sum": {
            "bits_per_second": 34_315_934, "bytes": 51_474_952,
            "packets": 35_549, "lost_packets": 24_397,
            "jitter_ms": 0.296,
        }},
        "server_output_json": json.dumps({
            "intervals": [
                {"sum": {"start": 0, "end": 1, "bits_per_second": 8_373_690,
                         "bytes": 1_046_904, "packets": 1712,
                         "lost_packets": 989, "jitter_ms": 0.318}},
                {"sum": {"start": 1, "end": 2, "bits_per_second": 9_000_000,
                         "bytes": 1_125_000, "packets": 1800,
                         "lost_packets": 1000, "jitter_ms": 0.300}}
            ],
            "end": {"sum": {
                "start": 0, "end": 12.022671, "seconds": 12.022671,
                "bits_per_second": 0, "bytes": 0,
                "packets": 34_363, "lost_packets": 24_397,
                "jitter_ms": 0.296, "sender": False,
            }},
        }),
    }

    result = parse_iperf3_json(client)
    assert result["receiver_report_source"] == "server"
    assert result["udp_packets"] == 34_363
    assert result["udp_lost_packets"] == 24_397
    assert result["udp_loss_pct"] == pytest.approx(100 * 24_397 / 34_363)
    assert result["receiver_goodput_mbps"] == pytest.approx(8.687616)
    assert result["receiver_bytes"] == 2_171_904
    assert result["receiver_duration_s"] == pytest.approx(2.0)

    intervals = parse_iperf3_intervals(client, "udp-flow")
    assert len(intervals) == 2
    assert intervals[0]["goodput_mbps"] == pytest.approx(8.373690)
    assert intervals[1]["goodput_mbps"] == pytest.approx(9.0)


def test_udp_fallback_only_pairs_bytes_with_their_interval_duration():
    import json

    payload = {
        "start": {"test_start": {"protocol": "UDP"}},
        "end": {"sum": {"bits_per_second": 0, "bytes": 0,
                         "packets": 100, "lost_packets": 0}},
        "server_output_json": json.dumps({
            "intervals": [
                {"sum": {"bytes": 1_000_000}},
                {"sum": {"start": 0, "end": 2}},
                None,
                {"sum": "malformed"},
                {"sum": {"start": 0, "end": 1, "bytes": 500_000}},
                {"sum": {"start": 1, "end": 1, "bytes": 700_000}},
                {"sum": {"start": 2, "end": 3, "bytes": float("nan")}},
            ],
            "end": {"sum": {
                "start": 0, "end": 3, "bits_per_second": 0, "bytes": 0,
                "packets": 100, "lost_packets": 0, "sender": False,
            }},
        }),
    }

    result = parse_iperf3_json(payload)

    assert result["receiver_bytes"] == 500_000
    assert result["receiver_duration_s"] == pytest.approx(1.0)
    assert result["receiver_goodput_mbps"] == pytest.approx(4.0)


def test_tcp_parser_prefers_server_receiver_and_preserves_sender_clock():
    import json

    client = {
        "start": {"test_start": {"protocol": "TCP"}},
        "end": {
            "sum_sent": {
                "start": 0.0, "end": 50.000232, "seconds": 50.000232,
                "bits_per_second": 7_877_000, "bytes": 49_231_640,
                "retransmits": 0,
            },
            "sum_received": {
                "start": 0.0, "end": 59.952188, "seconds": 59.952188,
                "bits_per_second": 6_569_000, "bytes": 49_231_640,
            },
        },
        "server_output_json": json.dumps({
            "intervals": [
                {"sum": {"start": 49.158712, "end": 59.966959,
                         "bits_per_second": 657_121.94, "bytes": 887_792,
                         "sender": False}}
            ],
            "end": {
                "sum_received": {
                    "start": 0.0, "end": 59.966959, "seconds": 59.966959,
                    "bits_per_second": 6_570_733.06, "bytes": 49_253_360,
                    "sender": False,
                }
            },
        }),
    }
    result = parse_iperf3_json(client)
    assert result["sender_goodput_mbps"] == pytest.approx(7.877)
    assert result["receiver_goodput_mbps"] == pytest.approx(6.57073306)
    assert result["goodput_mbps"] == result["receiver_goodput_mbps"]
    assert result["sender_bytes"] == 49_231_640
    assert result["receiver_bytes"] == 49_253_360
    assert result["sender_duration_s"] == pytest.approx(50.000232)
    assert result["receiver_duration_s"] == pytest.approx(59.966959)
    assert result["receiver_report_source"] == "server"

    intervals = parse_iperf3_intervals(client, "flow-a")
    assert len(intervals) == 1
    assert intervals[0]["goodput_mbps"] == pytest.approx(0.65712194)
    assert intervals[0]["start_s"] == pytest.approx(49.158712)


def test_tcp_parser_falls_back_when_server_report_is_missing_or_invalid():
    import json

    base = {
        "start": {"test_start": {"protocol": "TCP"}},
        "end": {
            "sum_sent": {"bits_per_second": 3_000_000, "bytes": 300},
            "sum_received": {"bits_per_second": 2_500_000, "bytes": 250},
        },
    }
    for raw in ("not-json", None):
        payload = {**base, "server_output_json": raw}
        result = parse_iperf3_json(payload)
        assert result["receiver_report_source"] == "client"
        assert result["goodput_mbps"] == pytest.approx(2.5)
        assert result["sender_goodput_mbps"] == pytest.approx(3.0)

def test_parse_kernel_tcp_rtt_and_qdisc_counters():
    assert parse_ss_tcp_rtt(" cubic rto:201 rtt:12.34/2.0 ato:40") == [12.34]
    stats = parse_tc_qdisc_stats(
        "Sent 1200 bytes 12 pkt (dropped 3, overlimits 4 requeues 0)\n"
        " backlog 500b 5p requeues 0"
    )
    assert stats["qdisc_packets"] == 12
    assert stats["qdisc_drops"] == 3
    assert stats["qdisc_overlimits"] == 4
    assert stats["qdisc_backlog_bytes"] == 500
    assert stats["qdisc_backlog_packets"] == 5


def test_parse_ovs_port_drop_counters():
    rows = parse_ovs_port_stats(
        "  port 2: rx pkts=10, bytes=1000, dropped=2, errs=0\n"
        "           tx pkts=9, bytes=900, dropped=1, errs=0"
    )
    assert rows[0]["port"] == 2
    assert rows[0]["rx_packets"] == 10
    assert rows[0]["tx_dropped"] == 1


def test_iperf3_interval_goodput_is_keyed_for_fairness():
    records = parse_iperf3_intervals({
        "intervals": [
            {"sum": {"start": 0, "end": 1, "bits_per_second": 2_000_000}},
            {"sum": {"start": 1, "end": 2, "bits_per_second": 4_000_000}},
        ]
    }, "flow-a")
    assert [row["window_id"] for row in records] == [0, 1]
    assert [row["goodput_mbps"] for row in records] == [2, 4]


def test_settling_time_rejects_gaps_in_telemetry_coverage():
    samples = [
        {"monotonic_time": 11, "utilization": .1},
        {"monotonic_time": 20, "utilization": .1},
        {"monotonic_time": 22, "utilization": .1},
    ]
    assert settling_time([10], samples, .2, 4, max_sample_gap_s=3) == ""


def test_parse_ovs_openflow13_named_port_header():
    rows = parse_ovs_port_stats("""OFPST_PORT reply (OF1.3) (xid=0x2):
 2(s2-eth2): rx pkts=10, bytes=1000, drop=2, errs=0
     tx pkts=9, bytes=900, drop=1, errs=0""")
    assert rows == [{
        "port": 2, "rx_packets": 10, "rx_bytes": 1000,
        "rx_dropped": 2, "rx_errors": 0,
        "tx_packets": 9, "tx_bytes": 900,
        "tx_dropped": 1, "tx_errors": 0,
    }]


def test_concurrent_fairness_does_not_double_count_split_intervals():
    fairness = aggregate_concurrent_flow_fairness([
        {"window_id": 0, "flow_id": "a", "goodput_mbps": 10, "overlap_seconds": .5},
        {"window_id": 0, "flow_id": "a", "goodput_mbps": 10, "overlap_seconds": .5},
        {"window_id": 0, "flow_id": "b", "goodput_mbps": 10, "overlap_seconds": 1},
    ])
    assert fairness == {0: 1.0}
