"""Apply scheduled Mininet path impairments and retain event evidence."""
from __future__ import annotations
import threading
import time

PATH_SWITCH = {"s1-s2-s4": "s2", "s1-s3-s4": "s3"}


class MininetImpairments:
    def __init__(self, net, ledger=None):
        self.net = net
        self.ledger = ledger
        self._stop = threading.Event()
        self._thread = None
        self.errors = []

    @staticmethod
    def interface_for(path):
        if path not in PATH_SWITCH:
            raise ValueError(f"unsupported path: {path}")
        return PATH_SWITCH[path], f"{PATH_SWITCH[path]}-eth2"

    def apply(self, event):
        paths = tuple(PATH_SWITCH) if event.path == "both" else (event.path,)
        for path in paths:
            switch, interface = self.interface_for(path)
            node = self.net.get(switch)
            if event.action == "set_rate":
                command = (f"tc qdisc replace dev {interface} root tbf "
                           f"rate {event.value} burst 32kbit latency 400ms")
            elif event.action == "set_delay":
                command = f"tc qdisc replace dev {interface} root netem delay {event.value}"
            elif event.action == "set_loss":
                command = f"tc qdisc replace dev {interface} root netem loss {event.value}"
            elif event.action == "link_down":
                command = f"ip link set dev {interface} down"
            elif event.action == "link_up":
                command = f"ip link set dev {interface} up"
            else:
                raise ValueError(f"unsupported impairment action: {event.action}")
            output = node.cmd(command)
            if output.strip():
                raise RuntimeError(f"impairment command failed: {command}: {output.strip()}")
            if self.ledger:
                self.ledger.record(
                    "impairment_event", path=path, action=event.action,
                    value=event.value, command=command,
                )

    def start(self, events, clock=time.monotonic, sleep=time.sleep):
        if self._thread is not None:
            raise RuntimeError("impairment schedule already started")
        schedule = sorted(events, key=lambda item: item.offset_s)
        origin = clock()

        def run():
            for event in schedule:
                remaining = origin + event.offset_s - clock()
                if remaining > 0 and self._stop.wait(remaining):
                    return
                if self._stop.is_set():
                    return
                try:
                    self.apply(event)
                except Exception as exc:
                    self.errors.append(str(exc))
                    if self.ledger:
                        self.ledger.record("impairment_error", error=str(exc))
                    self._stop.set()
                    return

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        return list(self.errors)
