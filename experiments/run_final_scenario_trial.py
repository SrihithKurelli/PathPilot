"""Run one complete proposal-aligned Mininet scenario trial."""
from __future__ import annotations
import argparse
import json
import os
import signal
import subprocess
import time
from pathlib import Path

from controller.event_ledger import EventLedger
from experiments.impairments import PATH_SWITCH
from experiments.mininet_policy_eval import ControllerLog
from experiments.network_sampling import NetworkStatsSampler
from experiments.runtime_metrics import ProcessMetricsSampler
from experiments.scenario_traffic import run_scenario
from experiments.scenarios import SCENARIO_NAMES, build_scenario, scenario_digest
from experiments.final_metrics import path_stability, settling_time


def read_events(path):
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def run_trial(policy, scenario_name, condition, initial_path, repetition,
              output_dir, *, seed=2027, bottleneck_rate="10mbit",
              controller_ip="127.0.0.1", controller_port=6653, venv=".venv",
              warmup_seconds=6.0):
    from topology.mininet_topology import build_network

    scenario = build_scenario(scenario_name, seed=seed)
    delay, noise = condition
    if warmup_seconds < max(4.0, delay + 4.0):
        raise ValueError("warmup must cover telemetry delay plus four seconds")
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    event_path = output_dir / "controller_events.jsonl"
    if event_path.exists():
        raise FileExistsError(f"refusing to overwrite event log: {event_path}")

    env = os.environ.copy()
    env.update({
        "PATHPILOT_POLICY": policy,
        "PATHPILOT_TELEMETRY_DELAY_S": str(delay),
        "PATHPILOT_TELEMETRY_NOISE_STD": str(noise),
        "PATHPILOT_TELEMETRY_SEED": str(seed),
        "PATHPILOT_EVENT_LOG": str(event_path),
        "PATHPILOT_EXPERIMENT_INITIAL_PATH": initial_path,
        "PATHPILOT_EXPERIMENT_FIRST_FLOW_PORT": "5300",
        "EVENTLET_NO_GREENDNS": "yes",
        "PYTHONPATH": str(Path.cwd()),
    })
    manager = Path(venv).expanduser().resolve() / "bin" / "ryu-manager"
    if not manager.is_file():
        raise FileNotFoundError(f"Ryu manager not found: {manager}")
    controller = subprocess.Popen(
        [str(manager), "controller/ryu_app.py"], cwd=Path.cwd(), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
    )
    controller_log = ControllerLog(controller.stdout)
    cpu = ProcessMetricsSampler(controller.pid).start()
    net = None
    sampler = None
    result = None
    parent_ledger = EventLedger(event_path)
    try:
        time.sleep(1.5)
        if controller.poll() is not None:
            raise RuntimeError("Ryu exited during startup: " + controller_log.text())
        net = build_network(controller_ip, controller_port)
        controller_log.wait_for(r"Live telemetry ready:", timeout=35)
        loss = net.pingAll()
        if loss != 0:
            raise RuntimeError(f"Mininet connectivity check failed: {loss}% loss")
        experiment_start = parent_ledger.record(
            "experiment_start", scenario=scenario_name, policy=policy,
            initial_path=initial_path, seed=seed,
        )["monotonic_time"]

        switch = PATH_SWITCH[initial_path]
        interface = f"{switch}-eth2"
        qdisc = net.get(switch).cmd(
            f"tc qdisc replace dev {interface} root tbf "
            f"rate {bottleneck_rate} burst 32kbit latency 400ms"
        )
        if qdisc.strip():
            raise RuntimeError(f"could not apply initial bottleneck: {qdisc}")
        time.sleep(warmup_seconds)

        sampler = NetworkStatsSampler(net, parent_ledger).start()
        traffic = run_scenario(
            net, scenario, output_dir / "traffic", parent_ledger,
        )
        sampler_errors = sampler.stop()
        cpu_metrics = cpu.stop()
        result = {
            "policy": policy,
            "scenario": scenario_name,
            "scenario_sha256": scenario_digest(scenario),
            "telemetry_delay_seconds": delay,
            "telemetry_noise_std": noise,
            "initial_bottleneck_path": initial_path,
            "bottleneck_rate": bottleneck_rate,
            "repetition": repetition,
            "seed": seed,
            "connectivity_loss_pct": loss,
            "experiment_start_monotonic": experiment_start,
            "traffic": traffic,
            "network_sampler_errors": sampler_errors,
            "controller_metrics": cpu_metrics,
            "controller_event_log": str(event_path),
            "git_revision": subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                check=False,
            ).stdout.strip(),
            "working_tree_dirty": int(bool(subprocess.run(
                ["git", "status", "--porcelain"], capture_output=True, text=True,
                check=False,
            ).stdout.strip())),
        }
    finally:
        if sampler is not None:
            sampler.stop()
        cpu.stop()
        if net is not None:
            net.stop()
        if controller.poll() is None:
            controller.terminate()
            try:
                controller.wait(timeout=5)
            except subprocess.TimeoutExpired:
                controller.kill()
                controller.wait(timeout=5)

    events = read_events(event_path)
    experiment_events = [
        event for event in events
        if float(event.get("monotonic_time", 0)) >= experiment_start
    ]
    decisions = [
        {"path": event["path"], "monotonic_time": event["monotonic_time"]}
        for event in experiment_events if event.get("event") == "path_decision"
    ]
    samples = [
        event for event in experiment_events if event.get("event") == "telemetry_sample"
    ]
    impairments = [
        event for event in experiment_events if event.get("event") == "impairment_event"
    ]
    telemetry_messages = [
        event for event in events
        if event.get("event") in {"telemetry_request", "telemetry_reply"}
    ]
    flow_mods = [event for event in events if event.get("event") == "flow_mod"]
    result["event_metrics"] = {
        **path_stability(decisions, window_seconds=10.0,
                          observation_duration_s=scenario.duration_s),
        "flow_mod_count": len(flow_mods),
        "telemetry_request_count": sum(e["event"] == "telemetry_request" for e in telemetry_messages),
        "telemetry_reply_count": sum(e["event"] == "telemetry_reply" for e in telemetry_messages),
        "telemetry_estimated_bytes": sum(int(e.get("estimated_bytes", 0)) for e in telemetry_messages),
        "telemetry_samples": len(samples),
        "impairment_event_count": len(impairments),
        "event_count": len(events),
    }
    adaptation = []
    for event in impairments:
        if event.get("action") not in {"set_rate", "link_up"}:
            continue
        path_samples = [
            {"monotonic_time": sample["monotonic_time"],
             "utilization": sample["utilization"]}
            for sample in samples if sample.get("path") == event.get("path")
        ]
        adaptation.append({
            "path": event.get("path"),
            "action": event.get("action"),
            "event_monotonic_time": event["monotonic_time"],
            "utilization_settling_time_s": settling_time(
                [event["monotonic_time"]], path_samples,
                utilization_threshold=.20, hold_seconds=4.0,
            ),
        })
    result["adaptation"] = adaptation
    result["controller_events"] = events
    target = output_dir / "trial_result.json"
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", required=True,
                        choices=("static", "least_loaded", "threshold",
                                 "stability_aware", "uncertainty_aware"))
    parser.add_argument("--scenario", required=True, choices=SCENARIO_NAMES)
    parser.add_argument("--condition", choices=("baseline", "delayed", "noisy", "combined"),
                        default="baseline")
    parser.add_argument("--initial-path", choices=("s1-s2-s4", "s1-s3-s4"),
                        required=True)
    parser.add_argument("--repetition", type=int, default=1)
    parser.add_argument("--seed", type=int, default=2027)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bottleneck-rate", default="10mbit")
    parser.add_argument("--controller-ip", default="127.0.0.1")
    parser.add_argument("--controller-port", type=int, default=6653)
    parser.add_argument("--venv", default=".venv")
    parser.add_argument("--warmup-seconds", type=float, default=6)
    args = parser.parse_args()
    conditions = {
        "baseline": (0.0, 0.0), "delayed": (2.0, 0.0),
        "noisy": (0.0, 0.05), "combined": (2.0, 0.05),
    }
    result = run_trial(
        args.policy, args.scenario, conditions[args.condition], args.initial_path,
        args.repetition, args.output_dir, seed=args.seed,
        bottleneck_rate=args.bottleneck_rate, controller_ip=args.controller_ip,
        controller_port=args.controller_port, venv=args.venv,
        warmup_seconds=args.warmup_seconds,
    )
    print(f"Completed {args.policy}/{args.scenario}/{args.condition}; "
          f"TCP app p99={result['traffic']['tcp_application_rtt']['tcp_app_rtt_ms_p99']} ms")


if __name__ == "__main__":
    main()
