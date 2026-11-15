# PathPilot

SDN routing under uncertain telemetry — a Computer Networks group project.

## Current implementation

PathPilot has a two-path Mininet topology and a Ryu OpenFlow 1.3 controller. For each new IPv4 TCP, UDP, or ICMP flow entering at s1, the controller selects one path and installs forwarding rules along it. The reverse direction is pinned to the selected path. Existing flows are not migrated.

The controller now polls OpenFlow port statistics every 2 seconds and derives utilization for the two internal links on each candidate path:

- `s1-s2-s4`: s1 port 2 and s2 port 2
- `s1-s3-s4`: s1 port 3 and s3 port 2

Utilization is calculated from transmit-byte counter deltas against the topology's configured 100 Mbps link capacity. A path's utilization is the maximum utilization of its two internal links, so a single heavily loaded hop is not hidden by averaging. Variability is the population standard deviation of up to five recent utilization samples per link.

The Mininet topology assigns stable OpenFlow DPIDs 1–4 to s1–s4 so the controller's port map is deterministic. Live telemetry is used only when both paths have fresh samples (no older than 6 seconds). Until then, or if measurements become stale, the controller falls back to `experiments/telemetry.json`. This keeps the prototype usable during controller startup and temporary statistics gaps.

## Layout

- `controller/policies.py`: pure routing-policy functions and confidence score
- `controller/live_telemetry.py`: OpenFlow counter-to-utilization calculations
- `controller/ryu_app.py`: Ryu controller, port-stat polling, path selection and flow installation
- `topology/mininet_topology.py`: two parallel Mininet paths
- `experiments/`: static fallback telemetry and proposed scenarios
- `tests/`: policy and live-telemetry unit tests
- `.github/workflows/tests.yml`: CI unit-test workflow

## Environment

Use Ubuntu 22.04 with Mininet, Open vSwitch, Python 3.10, and Ryu 4.34. Ryu/eventlet compatibility can vary by Python version; if installation fails, use a supported Python 3.10 environment.

```bash
sudo apt update
sudo apt install -y mininet openvswitch-switch iperf3 python3.10 python3.10-venv
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Run

Terminal 1:

```bash
source .venv/bin/activate
EVENTLET_NO_GREENDNS=yes ryu-manager controller/ryu_app.py
```

Terminal 2:

```bash
sudo python3 topology/mininet_topology.py --controller 127.0.0.1
```

The controller reads the static fallback from `experiments/telemetry.json` (override with `PATHPILOT_TELEMETRY`) and selects a policy using `PATHPILOT_POLICY`:
`static`, `least_loaded`, `threshold`, or `uncertainty_aware`.

## Unit tests

```bash
python -m pip install pytest
python -m pytest -q
```

These tests validate policy selection and the pure port-counter calculations. They do not replace end-to-end validation of Ryu event handling, OpenFlow statistics delivery, Mininet forwarding, or throughput under load.

## Research evaluation target

Compare policies under identical traffic and telemetry conditions. Report p99 latency, goodput, packet loss, Jain fairness (when applicable), path changes, controller CPU, rule updates, and telemetry volume. Use repeated trials and fixed seeds. Treat Mininet results as emulation measurements, not production-network measurements.

## Current limitations

- Port utilization assumes the configured 100 Mbps capacity and the documented Mininet port map.
- Live utilization is based on inter-switch transmit counters; it does not directly measure queue occupancy or delay.
- The static JSON is a fallback, not the primary source once live statistics are fresh.
- The controller does not migrate established flows after a path decision.
- Reverse-path state is in memory and is lost on controller restart.
- ARP remains statically populated by the Mininet topology; general ARP forwarding is not implemented.


## Policy evaluation

The repository includes a deterministic **synthetic telemetry replay** to compare
policy decisions independently of Mininet timing and traffic-generation noise. It
covers balanced load, either path being hot, changing load, noisy measurements,
and stale measurements. The replay reports selected-path utilization, regret
relative to an oracle that knows the simulated true utilization, oracle-choice
rate, and selected-sample confidence. These are simulation results, not measured
network performance.

Run from the repository root with the project virtual environment active:

```bash
python -m pytest -q
python experiments/policy_replay.py --seed 7 --trials 10 --steps 100
python experiments/analyze_results.py results/policy_replay.csv
```

The replay writes raw decisions to `results/policy_replay.csv` and grouped
summaries to `results/policy_summary.csv`. Change `--seed`, `--trials`, and
`--steps` to test repeatability and increase the number of simulated decisions.
Keep the seed and parameters with any reported result.

For the network-level evaluation, use the Mininet/Ryu topology separately:
measure each path under the same link capacity, delay, and offered load, repeat
each trial, and record iperf3 goodput plus ping RTT/loss. Do not label synthetic
replay outputs as throughput, latency, or packet-loss measurements. The current
controller selects a path only when a new flow arrives and does not migrate
established flows, so each policy/trial must start with cleared flow state and a
fresh controller process for a fair comparison.
