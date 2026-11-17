from types import SimpleNamespace

from experiments.network_sampling import NetworkStatsSampler


class FakeNode:
    def cmd(self, command):
        assert command.startswith("tc -s qdisc show")
        return "Sent 1200 bytes 12 pkt (dropped 3, overlimits 4 requeues 0) backlog 500b 5p"


class FakeNet:
    def get(self, name):
        return FakeNode()


class FakeLedger:
    def __init__(self):
        self.events = []

    def record(self, event, **fields):
        self.events.append((event, fields))


def test_network_sampler_records_qdisc_and_ovs_snapshots():
    ledger = FakeLedger()

    def run(command, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout=("  port 2: rx pkts=10, bytes=1000, drop=2, errs=0\n"
                    "           tx pkts=9, bytes=900, drop=1, errs=0"),
            stderr="",
        )

    sampler = NetworkStatsSampler(FakeNet(), ledger, command_runner=run)
    sampler.sample_once()
    assert len(ledger.events) == 4
    qdisc = ledger.events[0][1]["counters"]
    assert qdisc["qdisc_drops"] == 3
    ovs = ledger.events[1][1]["counters"]
    assert ovs[0]["rx_dropped"] == 2


def test_network_sampler_retains_counter_command_errors():
    ledger = FakeLedger()

    def run(command, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="not connected")

    sampler = NetworkStatsSampler(FakeNet(), ledger, command_runner=run)
    sampler.sample_once()
    assert len(sampler.errors) == 2
    assert all(event[0] == "counter_sample_error" for event in ledger.events[1::2])
