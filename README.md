# PathPilot

SDN routing under uncertain telemetry — a Computer Networks group project.

## Project status: early prototype

This repository currently contains a policy-selection core, a starter Ryu OpenFlow 1.3 application, a two-path Mininet topology, sample telemetry/scenario JSON, and unit tests.

**Not yet complete:** live switch/queue telemetry collection, delay/noise injection, robust bidirectional forwarding and ARP/ICMP handling, experiment automation, metric extraction, and end-to-end Mininet validation. The current telemetry JSON is a static snapshot; it is not collected from switches yet.

## Layout

- `controller/policies.py`: pure routing-policy functions and confidence score
- `controller/ryu_app.py`: starter Ryu controller for new IPv4 TCP/UDP flows
- `topology/mininet_topology.py`: two parallel Mininet paths
- `experiments/`: sample telemetry and proposed scenarios
- `tests/`: policy unit tests
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
ryu-manager controller/ryu_app.py
```

Terminal 2:
```bash
sudo python3 topology/mininet_topology.py --controller 127.0.0.1
```

The controller reads `experiments/telemetry.json` (override with `PATHPILOT_TELEMETRY`) and selects a policy using `PATHPILOT_POLICY`:
`static`, `least_loaded`, `threshold`, or `uncertainty_aware`.

## Unit tests

```bash
python -m pip install pytest
python -m pytest -q
```

These tests exercise only the pure policy logic. They do not validate Ryu, OpenFlow rules, Mininet, OVS, traffic forwarding, or performance.

## Research evaluation target

Compare policies under identical traffic and telemetry conditions. Report p99 latency, goodput, packet loss, Jain fairness (when applicable), path changes, controller CPU, rule updates, and telemetry volume. Use repeated trials and fixed seeds. Treat Mininet results as emulation measurements, not production-network measurements.
