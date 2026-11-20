import pytest

from experiments.impairments import MininetImpairments
from experiments.scenarios import ImpairmentEvent


class FakeNode:
    def __init__(self):
        self.commands = []

    def cmd(self, command):
        self.commands.append(command)
        return ""


class FakeNet:
    def __init__(self):
        self.nodes = {"s2": FakeNode(), "s3": FakeNode()}

    def get(self, name):
        return self.nodes[name]


def test_impairment_actions_target_the_selected_path():
    net = FakeNet()
    runner = MininetImpairments(
        net, rate_by_path={"s1-s2-s4": "10mbit", "s1-s3-s4": "100mbit"}
    )
    runner.apply(ImpairmentEvent(1, "s1-s2-s4", "set_rate", "5mbit"))
    runner.apply(ImpairmentEvent(2, "s1-s3-s4", "set_loss", "2%"))
    runner.apply(ImpairmentEvent(3, "s1-s2-s4", "link_down"))
    runner.apply(ImpairmentEvent(4, "s1-s2-s4", "link_up"))
    assert "rate 5mbit" in net.nodes["s2"].commands[0]
    assert "rate 100mbit" in net.nodes["s3"].commands[0]
    assert "loss 2%" in net.nodes["s3"].commands[1]
    assert net.nodes["s2"].commands[-2:] == [
        "ip link set dev s2-eth2 down", "ip link set dev s2-eth2 up"
    ]


def test_both_paths_are_applied_and_unknown_path_rejected():
    net = FakeNet()
    runner = MininetImpairments(
        net, rate_by_path={"s1-s2-s4": "10mbit", "s1-s3-s4": "100mbit"}
    )
    runner.apply(ImpairmentEvent(0, "both", "set_delay", "20ms"))
    assert len(net.nodes["s2"].commands) == 2
    assert len(net.nodes["s3"].commands) == 2
    with pytest.raises(ValueError):
        runner.interface_for("bad")


def test_loss_and_delay_are_composed_under_the_bottleneck():
    net = FakeNet()
    runner = MininetImpairments(
        net, rate_by_path={"s1-s2-s4": "10mbit", "s1-s3-s4": "100mbit"}
    )
    runner.apply(ImpairmentEvent(0, "s1-s2-s4", "set_loss", "5%"))
    runner.apply(ImpairmentEvent(1, "s1-s2-s4", "set_delay", "20ms"))
    commands = net.nodes["s2"].commands
    assert "rate 10mbit" in commands[0]
    assert "parent 1:1" in commands[1]
    assert "loss 5%" in commands[1]
    assert "delay 20ms" in commands[3]
    assert "loss 5%" in commands[3]
