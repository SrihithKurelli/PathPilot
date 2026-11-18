from types import SimpleNamespace

from experiments.scenario_traffic import build_iperf_command


def test_tcp_command_enforces_offered_rate():
    flow = SimpleNamespace(protocol="TCP", duration_s=50, offered_rate_mbps=8)
    command = build_iperf_command("10.0.0.2", 5300, flow)
    assert command == [
        "iperf3", "-c", "10.0.0.2", "-p", "5300",
        "-t", "50", "-J", "-b", "8M",
    ]


def test_udp_command_keeps_udp_rate_limit():
    flow = SimpleNamespace(protocol="UDP", duration_s=12, offered_rate_mbps=35)
    command = build_iperf_command("10.0.0.2", 5301, flow)
    assert command == [
        "iperf3", "-c", "10.0.0.2", "-p", "5301",
        "-t", "12", "-J", "-u", "-b", "35M",
    ]
