#!/usr/bin/env python3
"""Run repeatable Mininet comparisons with optional delayed/noisy telemetry.

Each trial starts a fresh Ryu controller and Mininet topology. The first TCP
flow selects a path; the harness bottlenecks that actual path, waits for the
configured telemetry delay plus warm-up, then measures one or more successive new flows.

This is an emulation experiment. It records TCP goodput/path decisions and a
concurrent ICMP probe's RTT percentiles and packet loss. The ICMP probe is a
separate flow and is not a per-TCP-flow latency measurement. Fairness and
controller overhead are not measured.
Run as root from the repository root on the configured Ubuntu/Mininet host.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path

from experiments.runtime_metrics import ProcessMetricsSampler, path_transition_metrics

POLICIES = ("static", "least_loaded", "threshold", "stability_aware", "uncertainty_aware")
PATH_TO_SWITCH = {"s1-s2-s4": "s2", "s1-s3-s4": "s3"}
BANDWIDTH_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s+([KMG])bits/sec")
PING_RTT_RE = re.compile(r"time[=<]([0-9]+(?:\.[0-9]+)?)\s*ms")
PING_LOSS_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)% packet loss")


class ControllerLog:
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

    def text(self, start=0):
        with self.condition:
            return "\n".join(self.lines[start:])

    def fallback_before(self, start, selection_line):
        """Return the fallback-decision log immediately before a flow selection."""
        with self.condition:
            decision_lines = self.lines[start:]
            try:
                decision_index = decision_lines.index(selection_line)
            except ValueError:
                return "FALLBACK_LOG_NOT_FOUND"
            candidates = [
                line for line in decision_lines[:decision_index]
                if "Uncertainty fallback:" in line
            ]
            return candidates[-1] if candidates else "NO_FALLBACK_USED"

    def telemetry_before(self, start, selection_line):
        """Return the latest telemetry-source log immediately before a decision."""
        telemetry_pattern = re.compile(
            r"Using LIVE telemetry:|Using STATIC telemetry fallback|"
            r"Telemetry unavailable"
        )
        with self.condition:
            decision_lines = self.lines[start:]
            try:
                decision_index = decision_lines.index(selection_line)
            except ValueError:
                return "TELEMETRY_LOG_NOT_FOUND"
            candidates = [
                line for line in decision_lines[:decision_index]
                if telemetry_pattern.search(line)
            ]
            return candidates[-1] if candidates else "TELEMETRY_LOG_NOT_FOUND"


def parse_iperf_mbps(output: str) -> float:
    matches = BANDWIDTH_RE.findall(output)
    if not matches:
        raise ValueError(f"Could not parse iperf bandwidth from output:\n{output}")
    value, unit = matches[-1]
    return float(value) * {"K": 0.001, "M": 1.0, "G": 1000.0}[unit]


def percentile(values, fraction):
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def parse_ping_metrics(output):
    """Parse ICMP probe RTT percentiles and packet loss from iputils ping."""
    rtts = [float(value) for value in PING_RTT_RE.findall(output)]
    loss_match = PING_LOSS_RE.search(output)
    if loss_match is None:
        raise ValueError(f"Could not parse packet loss from ping output:\\n{output}")
    return {
        "icmp_probe_packets": int(re.search(r"(\d+) packets transmitted", output).group(1)),
        "icmp_probe_packet_loss_pct": float(loss_match.group(1)),
        "icmp_probe_rtt_p50_ms": round(percentile(rtts, 0.50), 4) if rtts else "",
        "icmp_probe_rtt_p95_ms": round(percentile(rtts, 0.95), 4) if rtts else "",
        "icmp_probe_rtt_p99_ms": round(percentile(rtts, 0.99), 4) if rtts else "",
        "icmp_probe_rtt_samples": len(rtts),
    }


def repository_revision(repo_root):
    """Return the checked-out Git revision and whether the working tree is dirty."""
    try:
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True
        ).strip()
        status = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=repo_root, text=True
        )
        dirty = bool(status.strip())
        return revision, int(dirty)
    except (OSError, subprocess.CalledProcessError):
        return "unknown", -1


def _run_client(host, destination, port, duration):
    return host.popen(
        ["iperf", "-c", destination, "-p", str(port), "-t", str(duration)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
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
    from topology.mininet_topology import build_network

    venv = Path(args.venv).expanduser().resolve()
    ryu_manager = venv / "bin" / "ryu-manager"
    if not ryu_manager.is_file():
        raise FileNotFoundError(f"Cannot find {ryu_manager}; set --venv to the Ryu environment.")

    env = os.environ.copy()
    env.update({
        "PATHPILOT_POLICY": policy,
        "PYTHONPATH": str(repo_root),
        "EVENTLET_NO_GREENDNS": "yes",
        "PATHPILOT_TELEMETRY_DELAY_S": str(args.telemetry_delay_seconds),
        "PATHPILOT_TELEMETRY_NOISE_STD": str(args.telemetry_noise_std),
        # Same seed for all policies within a trial: policy comparisons see
        # the same deterministic noise stream for a given trial number.
        "PATHPILOT_TELEMETRY_SEED": str(args.seed + trial),
    })
    if args.initial_path is not None:
        env["PATHPILOT_EXPERIMENT_INITIAL_PATH"] = args.initial_path
        env["PATHPILOT_EXPERIMENT_FIRST_FLOW_PORT"] = str(args.first_flow_port)
    controller = subprocess.Popen(
        [str(ryu_manager), "controller/ryu_app.py"], cwd=repo_root, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
    )
    log = ControllerLog(controller.stdout)
    process_metrics = ProcessMetricsSampler(controller.pid).start()
    net = None
    servers = []
    first_client = second_client = ping_client = None
    qdisc_switch = None
    try:
        time.sleep(1.5)
        if controller.poll() is not None:
            raise RuntimeError("Ryu exited during startup:\n" + log.text())
        net = build_network(args.controller_ip, args.controller_port)
        log.wait_for(r"Live telemetry ready:", timeout=35)
        loss = net.pingAll()
        if loss != 0:
            raise RuntimeError(f"Mininet connectivity check failed: {loss:.1f}% loss")
        # Exclude the preliminary pingAll ICMP connectivity check from the
        # route-decision stability metrics; count only experiment TCP flows.
        experiment_log_mark = log.mark()

        h1, h2 = net.get("h1", "h2")
        fallback_ports = list(range(5002, 5002 + args.fallback_flow_count))
        for port in [5001, *fallback_ports]:
            servers.append(h2.popen(
                ["iperf", "-s", "-p", str(port)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            ))
        time.sleep(0.5)
        if any(server.poll() is not None for server in servers):
            raise RuntimeError("An iperf server exited; check that iperf is installed.")

        first_mark = log.mark()
        first_client = _run_client(h1, h2.IP(), 5001, args.first_flow_seconds)
        first_match, first_line = log.wait_for(
            r"Selected path (s1-s2-s4|s1-s3-s4) for new flow .*"
            + re.escape(f"(policy={policy})"), start=first_mark, timeout=20,
        )
        first_path = first_match.group(1)
        if args.initial_path is not None and first_path != args.initial_path:
            raise RuntimeError(
                f"Controller selected {first_path} despite requested initial path "
                f"{args.initial_path}"
            )
        first_telemetry_log = (
            "EXPERIMENT_PATH_PIN_NO_TELEMETRY_READ"
            if args.initial_path is not None
            else log.telemetry_before(first_mark, first_line)
        )
        qdisc_switch = PATH_TO_SWITCH[first_path]
        interface = f"{qdisc_switch}-eth2"
        qdisc_result = net.get(qdisc_switch).cmd(
            f"tc qdisc replace dev {interface} root tbf "
            f"rate {args.bottleneck_rate} burst 32kbit latency 400ms"
        )
        if qdisc_result.strip():
            raise RuntimeError(f"Could not apply bottleneck on {interface}: {qdisc_result}")

        # The warm-up must cover both the deliberate delay and multiple polls.
        time.sleep(args.warmup_seconds)
        fallback_paths = []
        fallback_goodputs = []
        fallback_returncodes = []
        fallback_reason_logs = []
        second_telemetry_log = "NOT_CAPTURED"
        ping_output = ""
        ping_returncode = -1

        # Send multiple distinct new TCP flows through the same controller.
        # This exposes fallback distribution across successive decisions.
        for flow_index, port in enumerate(fallback_ports):
            flow_mark = log.mark()
            client = _run_client(h1, h2.IP(), port, args.second_flow_seconds)
            second_client = client
            match, selection_line = log.wait_for(
                r"Selected path (s1-s2-s4|s1-s3-s4) for new flow .*"
                + re.escape(f"(policy={policy})"), start=flow_mark, timeout=20,
            )
            selected_path = match.group(1)
            fallback_reason_logs.append(
                log.fallback_before(flow_mark, selection_line)
            )
            if flow_index == 0:
                second_telemetry_log = log.telemetry_before(flow_mark, selection_line)
                # Probe RTT/loss concurrently with the first fallback flow.
                ping_client = h1.popen(
                    ["ping", "-n", "-i", "0.05", "-c", str(args.ping_count), h2.IP()],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                )
                second_path = selected_path
                second_line = selection_line
                second_client = client
            output, _ = client.communicate(timeout=args.second_flow_seconds + 20)
            returncode = client.returncode
            goodput = round(parse_iperf_mbps(output), 4)
            fallback_paths.append(selected_path)
            fallback_goodputs.append(goodput)
            fallback_returncodes.append(returncode)
            if flow_index == 0:
                second_output = output
                second_returncode = returncode
                second_client = None

        process_metrics.stop()
        if ping_client is not None:
            ping_output, _ = ping_client.communicate(timeout=args.second_flow_seconds + 20)
            ping_returncode = ping_client.returncode
            ping_client = None
        ping_metrics = parse_ping_metrics(ping_output)
        first_output, _ = first_client.communicate(
            timeout=max(5, args.first_flow_seconds - args.warmup_seconds
                       - args.second_flow_seconds + 25)
        )
        first_returncode = first_client.returncode
        first_client = None
        git_revision, working_tree_dirty = repository_revision(repo_root)
        selected_paths = re.findall(
            r"Selected path (s1-s2-s4|s1-s3-s4) for new flow",
            log.text(start=experiment_log_mark),
        )
        route_metrics = path_transition_metrics(selected_paths)
        resource_metrics = process_metrics.stop()
        return {
            "policy": policy, "trial": trial, "seed": args.seed + trial,
            "git_revision": git_revision,
            "working_tree_dirty": working_tree_dirty,
            "requested_initial_path": args.initial_path or "policy_selected",
            "telemetry_delay_seconds": args.telemetry_delay_seconds,
            "telemetry_noise_std": args.telemetry_noise_std,
            "connectivity_loss_pct": loss,
            "first_flow_path": first_path, "bottleneck_path": first_path,
            "bottleneck_interface": interface, "bottleneck_rate": args.bottleneck_rate,
            "second_flow_path": second_path,
            "avoided_bottleneck": int(second_path != first_path),
            "second_flow_mbps": round(parse_iperf_mbps(second_output), 4),
            "fallback_flow_count": len(fallback_paths),
            "fallback_flow_paths": json.dumps(fallback_paths),
            "fallback_flow_goodputs_mbps": json.dumps(fallback_goodputs),
            "fallback_flow_client_returncodes": json.dumps(fallback_returncodes),
            "fallback_flow_reason_logs": json.dumps(fallback_reason_logs),
            "fallback_flow_avoidance_rate": round(
                sum(path != first_path for path in fallback_paths) / len(fallback_paths), 4
            ),
            **ping_metrics,
            "icmp_probe_returncode": ping_returncode,
            "first_flow_mbps": round(parse_iperf_mbps(first_output), 4),
            # Preserve complete client output and exit status for post-run diagnosis.
            # CSV quoting safely handles the embedded newlines in iperf output.
            "first_flow_client_returncode": first_returncode,
            "second_flow_client_returncode": second_returncode,
            "first_flow_iperf_output": first_output.strip(),
            "second_flow_iperf_output": second_output.strip(),
            "warmup_seconds": args.warmup_seconds,
            "first_selection_log": first_line, "second_selection_log": second_line,
            "first_telemetry_log": first_telemetry_log,
            "second_telemetry_log": second_telemetry_log,
            **route_metrics,
            **resource_metrics,
        }
    finally:
        if ping_client is not None:
            _stop_process(ping_client)
        if second_client is not None:
            _stop_process(second_client)
        if first_client is not None:
            _stop_process(first_client)
        if net is not None:
            if qdisc_switch is not None:
                net.get(qdisc_switch).cmd(
                    f"tc qdisc del dev {qdisc_switch}-eth2 root 2>/dev/null || true"
                )
            for server in servers:
                _stop_process(server)
            net.stop()
        _stop_process(controller)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policies", nargs="+", choices=POLICIES, default=list(POLICIES))
    parser.add_argument("--initial-path", choices=("s1-s2-s4", "s1-s3-s4"),
                        default=None,
                        help="pin only the first flow to this path; the second flow uses the policy")
    parser.add_argument("--first-flow-port", type=int, default=5001)
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--first-flow-seconds", type=int, default=25)
    parser.add_argument("--warmup-seconds", type=float, default=6.0)
    parser.add_argument("--second-flow-seconds", type=int, default=8)
    parser.add_argument(
        "--fallback-flow-count", type=int, default=1,
        help="number of successive policy-selected TCP flows after the pinned flow",
    )
    parser.add_argument("--ping-count", type=int, default=100,
                        help="number of concurrent ICMP RTT/loss probes")
    parser.add_argument("--bottleneck-rate", default="10mbit")
    parser.add_argument("--telemetry-delay-seconds", type=float, default=0.0)
    parser.add_argument("--telemetry-noise-std", type=float, default=0.0,
                        help="Gaussian utilization noise standard deviation, in [0,1]")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--controller-ip", default="127.0.0.1")
    parser.add_argument("--controller-port", type=int, default=6653)
    parser.add_argument("--venv", default=".venv")
    parser.add_argument("--output", type=Path, default=Path("results/mininet_policy_results.csv"))
    args = parser.parse_args()

    if args.ping_count < 1:
        parser.error("--ping-count must be positive")
    if args.trials < 1:
        parser.error("--trials must be positive")
    if args.fallback_flow_count < 1:
        parser.error("--fallback-flow-count must be positive")
    if 5001 + args.fallback_flow_count > 65535:
        parser.error("--fallback-flow-count exceeds available TCP destination ports")
    if not 1 <= args.first_flow_port <= 65535:
        parser.error("--first-flow-port must be in [1,65535]")
    required_background = (
        args.warmup_seconds + args.fallback_flow_count * args.second_flow_seconds
    )
    if args.first_flow_seconds <= required_background:
        parser.error(
            "--first-flow-seconds must exceed warmup + all fallback-flow durations "
            "so the pinned bottleneck flow remains active"
        )
    if args.telemetry_delay_seconds < 0:
        parser.error("--telemetry-delay-seconds must be non-negative")
    if not 0 <= args.telemetry_noise_std <= 1:
        parser.error("--telemetry-noise-std must be in [0,1]")
    if args.warmup_seconds < max(4.0, args.telemetry_delay_seconds + 4.0):
        parser.error("--warmup-seconds must be at least max(4, telemetry delay + 4)")

    repo_root = Path.cwd().resolve()
    rows = []
    for policy in args.policies:
        for trial in range(1, args.trials + 1):
            print(f"\n=== policy={policy} trial={trial}/{args.trials} "
                  f"delay={args.telemetry_delay_seconds}s noise={args.telemetry_noise_std} ===",
                  flush=True)
            row = run_trial(policy, trial, args, repo_root)
            rows.append(row)
            print(
                f"first path={row['first_flow_path']}; second path={row['second_flow_path']}; "
                f"second-flow goodput={row['second_flow_mbps']:.2f} Mbps; "
                f"avoided bottleneck={bool(row['avoided_bottleneck'])}", flush=True,
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote {len(rows)} Mininet trials to {args.output}", flush=True)


if __name__ == "__main__":
    main()
