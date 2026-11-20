"""Apply scheduled Mininet path impairments and retain event evidence."""
from __future__ import annotations
import threading
import time

PATH_SWITCH = {"s1-s2-s4": "s2", "s1-s3-s4": "s3"}


class MininetImpairments:
    def __init__(self, net, ledger=None, *, rate_by_path=None):
        self.net = net
        self.ledger = ledger
        self.rate_by_path = dict(rate_by_path or {})
        self.netem_options = {path: {} for path in PATH_SWITCH}
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
            commands = []
            if event.action == "set_rate":
                commands.append(
                    f"tc qdisc replace dev {interface} root handle 1: tbf "
                    f"rate {event.value} burst 32kbit latency 400ms"
                )
            elif event.action == "set_delay":
                self.netem_options[path]["delay"] = event.value
                commands = self._netem_commands(path, interface)
            elif event.action == "set_loss":
                self.netem_options[path]["loss"] = event.value
                commands = self._netem_commands(path, interface)
            elif event.action == "link_down":
                commands.append(f"ip link set dev {interface} down")
            elif event.action == "link_up":
                commands.append(f"ip link set dev {interface} up")
            else:
                raise ValueError(f"unsupported impairment action: {event.action}")
            command_results = []
            for command in commands:
                command_results.append(self._execute(node, command))
            if self.ledger:
                self.ledger.record(
                    "impairment_event", path=path, action=event.action,
                    value=event.value, command="; ".join(commands),
                    command_results=command_results,
                )

    @staticmethod
    def _execute(node, command):
        """Run a Mininet command and judge success by its exit status.

        ``Node.cmd`` returns merged command output without an exit code. Commands
        such as ``ip link set ... up`` can print informational qdisc state while
        succeeding, so non-empty output is not a reliable failure signal.
        ``Node.pexec`` returns stdout, stderr, and the actual status.
        """
        pexec = getattr(node, "pexec", None)
        if callable(pexec):
            stdout, stderr, returncode = pexec(command)
            result = {
                "command": command,
                "stdout": stdout,
                "stderr": stderr,
                "returncode": int(returncode),
            }
            if returncode != 0:
                detail = "\n".join(part.strip() for part in (stdout, stderr) if part.strip())
                raise RuntimeError(
                    f"impairment command failed (exit {returncode}): {command}"
                    + (f": {detail}" if detail else "")
                )
            return result

        # Lightweight fakes used by callers may expose only Node.cmd. Keep the
        # compatibility path, while production Mininet nodes use pexec above.
        output = node.cmd(command)
        if output.strip():
            raise RuntimeError(f"impairment command failed: {command}: {output.strip()}")
        return {"command": command, "stdout": output, "stderr": "", "returncode": None}

    def _netem_commands(self, path, interface):
        rate = self.rate_by_path.get(path)
        if not rate:
            raise ValueError(f"a baseline rate is required to impair {path}")
        options = self.netem_options[path]
        netem = " ".join(f"{key} {value}" for key, value in options.items())
        return [
            f"tc qdisc replace dev {interface} root handle 1: tbf "
            f"rate {rate} burst 32kbit latency 400ms",
            f"tc qdisc replace dev {interface} parent 1:1 handle 10: "
            f"netem {netem}",
        ]

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
