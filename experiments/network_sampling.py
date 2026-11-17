"""Periodic Mininet qdisc and OpenFlow port counter sampling."""
from __future__ import annotations
import subprocess
import threading
import time

from experiments.final_metrics import parse_ovs_port_stats, parse_tc_qdisc_stats
from experiments.impairments import PATH_SWITCH


class NetworkStatsSampler:
    def __init__(self, net, ledger, interval_s=0.5, command_runner=subprocess.run):
        if interval_s <= 0:
            raise ValueError("interval_s must be positive")
        self.net = net
        self.ledger = ledger
        self.interval_s = interval_s
        self.command_runner = command_runner
        self.stop_event = threading.Event()
        self.thread = None
        self.errors = []

    def sample_once(self):
        for path, switch in PATH_SWITCH.items():
            interface = f"{switch}-eth2"
            node = self.net.get(switch)
            qdisc_text = node.cmd(f"tc -s qdisc show dev {interface}")
            qdisc = parse_tc_qdisc_stats(qdisc_text)
            self.ledger.record(
                "qdisc_sample", path=path, switch=switch, interface=interface,
                counters=qdisc, source="tc -s qdisc",
            )
            result = self.command_runner(
                ["ovs-ofctl", "-O", "OpenFlow13", "dump-ports", switch],
                capture_output=True, text=True, check=False,
            )
            if result.returncode == 0:
                ports = parse_ovs_port_stats(result.stdout)
                self.ledger.record(
                    "ovs_port_sample", path=path, switch=switch,
                    counters=ports, source="ovs-ofctl dump-ports",
                )
            else:
                message = result.stderr.strip() or f"ovs-ofctl exit {result.returncode}"
                self.errors.append(message)
                self.ledger.record(
                    "counter_sample_error", path=path, source="ovs-ofctl dump-ports",
                    error=message,
                )

    def start(self):
        if self.thread is not None:
            raise RuntimeError("sampler already started")

        def loop():
            while not self.stop_event.is_set():
                try:
                    self.sample_once()
                except Exception as exc:
                    self.errors.append(str(exc))
                    self.ledger.record("counter_sample_error", error=str(exc))
                self.stop_event.wait(self.interval_s)

        self.thread = threading.Thread(target=loop, daemon=True)
        self.thread.start()
        return self

    def stop(self):
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=max(1.0, self.interval_s * 3))
        return list(self.errors)
