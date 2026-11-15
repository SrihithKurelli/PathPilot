#!/usr/bin/env python3
"""Run repeatable, closed-loop Mininet comparisons of PathPilot policies.

Each trial starts a fresh Ryu controller and Mininet topology. A first TCP
flow is allowed to select and occupy one path; the harness then applies the
same bottleneck to that *actual selected path*, waits for live telemetry to
observe it, and launches a second TCP flow. This avoids assuming that every
policy initially selects s1-s2-s4.

This is an emulation experiment. It records iperf goodput and controller
decisions; it does not measure p99 latency, fairness, or production behavior.
Run as root from the repository root on the configured Ubuntu/Mininet host.
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import subprocess
import threading
import time
from pathlib import Path

POLICIES = ("static", "least_loaded", "threshold", "uncertainty_aware")
PATH_TO_SWITCH = {"s1-s2-s4": "s2", "s1-s3-s4": "s3"}
SELECTION_RE = re.compile(
    r"Selected path (s1-s2-s4|s1-s3-s4) for new flow .*?\(policy=([a-z_]+)\)"
)
BANDWIDTH_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s+([KMG])bits/sec")


class ControllerLog:
    """Read controller output continuously and wait for ordered decisions."""

    def __init__(self, stream):
        self.lines = []
        self.condition = threading.Condition()
        self.thread = threading.Thread(target=self._read, args=(stream,), daemon=True)
        self.thread.start()

    def _read(self, stream):
        for line in iter(stream.readline, ""):
            with self.condition:
                self.lines.append(line.rstrip())
                self.condition.notify_all()

    def mark(self):
        with self.condition:
            return len(self.lines)

    def wait_for(self, pattern, start=0, timeout=30):
        regex = re.compile(pattern)
        deadline = time.monotonic() + timeout
        with self.condition:
            while True:
                for line in self.lines[start:]:
                    match = regex.search(line)
                    if match:
                        return match, line
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    tail = "\n".join(self.lines[-30:])
                    raise TimeoutError(
                        f"Timed out waiting for controller log /{pattern}/. "
                        f"Recent controller output:\n{tail}"
                    )
                self.condition.wait(remaining)

    def text(self):
        with self.condition:
            return "\n".join(self.lines)


def parse_iperf_mbps(output: str) -> float:
    """Extract the final iperf 2 bandwidth line and normalize to Mbps."""
    matches = BANDWIDTH_RE.findall(output)
    if not matches:
        raise ValueError(f"Could not parse iperf bandwidth from output:\n{output}")
    value, unit = matches[-1]
    multiplier = {"K": 0.001, "M": 1.0, "G": 1000.0}[unit]
    return float(value) * multiplier


def _run_client(host, destination, port, duration):
    return host.popen(
        ["iperf", "-c", destination, "-p", str(port), "-t", str(duration)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _stop_process(process):
    if process is None:
        return
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


def run_trial(policy, trial, args, repo_root):
    # Import only inside the runtime path: ordinary unit tests and CI do not
    # need Mininet installed.
    from topology.mininet_topology import build_network

    venv = Path(args.venv).expanduser().resolve()
    ryu_manager = venv / "bin" / "ryu-manager"
    if not ryu_manager.is_file():
        raise FileNotFoundError(
            f"Cannot find {ryu_manager}. Set --venv to the project Python "
            "environment containing Ryu."
        )

    env = os.environ.copy()
    env.update({
        "PATHPILOT_POLICY": policy,
        "PYTHONPATH": str(repo_root),
        "EVENTLET_NO_GREENDNS": "yes",
    })
    controller = subprocess.Popen(
        [str(ryu_manager), "controller/ryu_app.py"],
        cwd=repo_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    log = ControllerLog(controller.stdout)
    net = None
    servers = []
    first_client = None
    second_client = None
    qdisc_switch = None
    try:
        # Start switches only after the controller listener is available.
        time.sleep(1.5)
        if controller.poll() is not None:
            raise RuntimeError("Ryu exited during startup:\n" + log.text())

        net = build_network(args.controller_ip, args.controller_port)
        ready, _ = log.wait_for(r"Live telemetry ready:", timeout=35)
        del ready

        loss = net.pingAll()
        if loss != 0:
            raise RuntimeError(f"Mininet connectivity check failed: {loss:.1f}% loss")

        h1, h2 = net.get("h1", "h2")
        for port in (5001, 5002):
            server = h2.popen(
                ["iperf", "-s", "-p", str(port)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            servers.append(server)
        time.sleep(0.5)
        if any(server.poll() is not None for server in servers):
            raise RuntimeError("An iperf server exited; check that iperf is installed.")

        # Start a new TCP flow and identify the path actually selected by Ryu.
        first_mark = log.mark()
        first_client = _run_client(h1, h2.IP(), 5001, args.first_flow_seconds)
        first_match, first_line = log.wait_for(
            r"Selected path (s1-s2-s4|s1-s3-s4) for new flow .*"
            + re.escape(f"(policy={policy})"),
            start=first_mark,
            timeout=20,
        )
        first_path = first_match.group(1)
        qdisc_switch = PATH_TO_SWITCH[first_path]
        interface = f"{qdisc_switch}-eth2"
        qdisc_cmd = (
            f"tc qdisc replace dev {interface} root tbf "
            f"rate {args.bottleneck_rate} burst 32kbit latency 400ms"
        )
        qdisc_result = net.get(qdisc_switch).cmd(qdisc_cmd)
        if qdisc_result.strip():
            raise RuntimeError(f"Could not apply bottleneck on {interface}: {qdisc_result}")

        # Wait across multiple 2-second OpenFlow polling intervals so the
        # controller can observe the bottleneck before the second decision.
        time.sleep(args.warmup_seconds)
        second_mark = log.mark()
        second_client = _run_client(h1, h2.IP(), 5002, args.second_flow_seconds)
        second_match, second_line = log.wait_for(
            r"Selected path (s1-s2-s4|s1-s3-s4) for new flow .*"
            + re.escape(f"(policy={policy})"),
            start=second_mark,
            timeout=20,
        )
        second_path = second_match.group(1)

        second_output, _ = second_client.communicate(
            timeout=args.second_flow_seconds + 20
        )
        second_client = None
        first_output, _ = first_client.communicate(
            timeout=max(5, args.first_flow_seconds - args.warmup_seconds
                       - args.second_flow_seconds + 25)
        )
        first_client = None
        return {
            "policy": policy,
            "trial": trial,
            "connectivity_loss_pct": loss,
            "first_flow_path": first_path,
            "bottleneck_path": first_path,
            "bottleneck_interface": interface,
            "bottleneck_rate": args.bottleneck_rate,
            "second_flow_path": second_path,
            "avoided_bottleneck": int(second_path != first_path),
            "second_flow_mbps": round(parse_iperf_mbps(second_output), 4),
            "first_flow_mbps": round(parse_iperf_mbps(first_output), 4),
            "warmup_seconds": args.warmup_seconds,
            "first_selection_log": first_line,
            "second_selection_log": second_line,
        }
    finally:
        if second_client is not None:
            _stop_process(second_client)
        if first_client is not None:
            _stop_process(first_client)
        if net is not None:
            if qdisc_switch is not None:
                interface = f"{qdisc_switch}-eth2"
                net.get(qdisc_switch).cmd(
                    f"tc qdisc del dev {interface} root 2>/dev/null || true"
                )
            for server in servers:
                _stop_process(server)
            net.stop()
        _stop_process(controller)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policies", nargs="+", choices=POLICIES,
                        default=list(POLICIES))
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--first-flow-seconds", type=int, default=25)
    parser.add_argument("--warmup-seconds", type=float, default=6.0)
    parser.add_argument("--second-flow-seconds", type=int, default=8)
    parser.add_argument("--bottleneck-rate", default="10mbit")
    parser.add_argument("--controller-ip", default="127.0.0.1")
    parser.add_argument("--controller-port", type=int, default=6653)
    parser.add_argument("--venv", default=".venv",
                        help="project virtual environment containing ryu-manager")
    parser.add_argument("--output", type=Path,
                        default=Path("results/mininet_policy_results.csv"))
    args = parser.parse_args()

    if args.trials < 1:
        parser.error("--trials must be positive")
    if args.first_flow_seconds <= args.warmup_seconds + args.second_flow_seconds:
        parser.error(
            "--first-flow-seconds must exceed warmup + second-flow duration"
        )
    if args.warmup_seconds < 4:
        parser.error("--warmup-seconds must be at least 4 for 2-second polling")

    repo_root = Path.cwd().resolve()
    rows = []
    for policy in args.policies:
        for trial in range(1, args.trials + 1):
            print(f"\n=== policy={policy} trial={trial}/{args.trials} ===", flush=True)
            row = run_trial(policy, trial, args, repo_root)
            rows.append(row)
            print(
                f"first path={row['first_flow_path']}; "
                f"second path={row['second_flow_path']}; "
                f"second-flow goodput={row['second_flow_mbps']:.2f} Mbps; "
                f"avoided bottleneck={bool(row['avoided_bottleneck'])}",
                flush=True,
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote {len(rows)} Mininet trials to {args.output}", flush=True)


if __name__ == "__main__":
    main()
