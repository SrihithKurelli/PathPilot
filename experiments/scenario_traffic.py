"""Concurrent TCP/UDP workload execution for proposal scenarios.

The caller owns Mininet/controller lifecycle. iperf3 is required on both hosts.
"""
from __future__ import annotations
import json
import math
import threading
import time
from pathlib import Path

from experiments.final_metrics import (
    aggregate_concurrent_flow_fairness, parse_iperf3_intervals,
    parse_iperf3_json, summarize_distribution,
)
from experiments.impairments import MininetImpairments


def build_iperf_command(destination, port, flow):
    """Build an iperf3 command that respects each flow's offered rate."""
    command = ["iperf3", "-c", destination, "-p", str(port),
               "-t", str(math.ceil(flow.duration_s)), "-J",
               "--get-server-output"]
    if flow.protocol == "UDP":
        command.extend(["-u", "-b", f"{flow.offered_rate_mbps}M"])
    else:
        # iperf3 TCP pacing is required: without -b, TCP saturates the link
        # and the scenario's offered_rate_mbps is silently ignored.
        command.extend(["-b", f"{flow.offered_rate_mbps}M"])
    return command


def run_scenario(net, scenario, output_dir, ledger, *, base_port=5300,
                 echo_port=5199, echo_rate_hz=10, include_rtt_probe=True):
    h1, h2 = net.get("h1", "h2")
    destination = h2.IP()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if "iperf3" not in h1.cmd("command -v iperf3").strip():
        raise RuntimeError("iperf3 is required inside Mininet hosts; install iperf3")
    if "iperf3" not in h2.cmd("command -v iperf3").strip():
        raise RuntimeError("iperf3 is required inside Mininet hosts; install iperf3")

    servers = []
    clients = {}
    launch_errors = []
    lock = threading.Lock()
    for index, flow in enumerate(scenario.flows):
        port = base_port + index
        servers.append(h2.popen(
            ["iperf3", "-s", "-1", "-p", str(port), "-J"],
            stdout=None, stderr=None,
        ))
    echo_script = Path(__file__).with_name("tcp_echo.py")
    echo_server = None
    if include_rtt_probe:
        echo_server = h2.popen([
            "python3", str(echo_script), "server", "--port", str(echo_port)
        ])
    time.sleep(.5)
    if (include_rtt_probe and echo_server.poll() is not None) or any(
            server.poll() is not None for server in servers):
        raise RuntimeError("A traffic server exited during startup")

    impairment_runner = MininetImpairments(net, ledger).start(scenario.impairments)
    rtt_output = output_dir / "tcp_application_rtt.json"
    rtt_client = None
    origin = time.monotonic()

    def launch_flow(index, flow):
        delay = origin + flow.start_offset_s - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        port = base_port + index
        command = build_iperf_command(destination, port, flow)
        process = h1.popen(command, stdout=-1, stderr=-2, text=True)
        with lock:
            clients[index] = (process, flow, port, time.monotonic())

    launch_threads = [
        threading.Thread(target=launch_flow, args=(i, flow), daemon=True)
        for i, flow in enumerate(scenario.flows)
    ]
    for thread in launch_threads:
        thread.start()
    # Let the designated pinned priming flow reach the controller before the
    # separate RTT probe creates its own policy decision.
    time.sleep(.2)
    if include_rtt_probe:
        rtt_client = h1.popen([
            "python3", str(echo_script), "client", "--host", destination,
            "--port", str(echo_port), "--duration", str(scenario.duration_s),
            "--rate-hz", str(echo_rate_hz), "--output", str(rtt_output),
        ])
    for thread in launch_threads:
        thread.join()

    flow_results = []
    interval_records = []
    for index in range(len(scenario.flows)):
        process, flow, port, launched_at = clients[index]
        stdout, _ = process.communicate(timeout=math.ceil(flow.duration_s) + 25)
        if process.returncode != 0:
            raise RuntimeError(
                f"iperf3 client failed for flow {index} (port {port}, rc={process.returncode}): "
                + (stdout or "")[-2000:]
            )
        result = parse_iperf3_json(stdout)
        result.update({
            "flow_id": f"flow-{index:03d}",
            "flow_class": flow.flow_class,
            "protocol": flow.protocol,
            "port": port,
            "start_offset_s": flow.start_offset_s,
            "duration_s": flow.duration_s,
            "offered_rate_mbps": flow.offered_rate_mbps,
            "client_returncode": process.returncode,
            "iperf3_json": stdout,
        })
        flow_results.append(result)
        for interval in parse_iperf3_intervals(stdout, result["flow_id"]):
            actual_offset = launched_at - origin
            global_start = actual_offset + float(interval["start_s"])
            global_end = actual_offset + float(interval["end_s"])
            for window in range(int(global_start), int(math.ceil(global_end))):
                overlap = min(global_end, window + 1) - max(global_start, window)
                if overlap > 0:
                    interval_records.append({
                        **interval,
                        "window_id": window,
                        "overlap_seconds": overlap,
                        "goodput_mbps": float(interval["goodput_mbps"]),
                    })

    rtt_values = []
    if include_rtt_probe:
        rtt_stdout, _ = rtt_client.communicate(timeout=scenario.duration_s + 20)
        if rtt_client.returncode != 0 or not rtt_output.is_file():
            raise RuntimeError("TCP application RTT probe failed: " + (rtt_stdout or "")[-2000:])
        rtt_data = json.loads(rtt_output.read_text(encoding="utf-8"))
        rtt_values = [sample["rtt_ms"] for sample in rtt_data["rtt_samples"]]
    fairness = aggregate_concurrent_flow_fairness(interval_records)
    impairment_errors = impairment_runner.stop()
    for server in servers + ([echo_server] if echo_server is not None else []):
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=2)
            except Exception:
                server.kill()
                server.wait(timeout=2)

    result = {
        "scenario": scenario.manifest(),
        "flow_results": flow_results,
        "concurrent_interval_records": interval_records,
        "jain_fairness_by_second": fairness,
        "jain_fairness_mean": (sum(fairness.values()) / len(fairness) if fairness else ""),
        "tcp_application_rtt": summarize_distribution(rtt_values, "tcp_app_rtt_ms"),
        "tcp_application_rtt_samples": len(rtt_values),
        "impairment_errors": impairment_errors,
        "tcp_rtt_probe_output": str(rtt_output) if include_rtt_probe else "",
    }
    (output_dir / "scenario_result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    ledger.record(
        "scenario_complete", scenario=scenario.name,
        flow_count=len(flow_results), tcp_rtt_samples=len(rtt_values),
        fairness_windows=len(fairness), impairment_errors=len(impairment_errors),
    )
    return result
