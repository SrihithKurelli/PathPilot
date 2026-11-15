# PathPilot — Path Selection and Bottleneck Experiment

## 1. Objective

Evaluate whether PathPilot selects paths according to supplied telemetry and whether a bandwidth bottleneck on one path affects its measured throughput.

The topology contains two parallel paths between h1 and h2:

- Path 1: h1 → s1 → s2 → s4 → h2
- Path 2: h1 → s1 → s3 → s4 → h2

## 2. Experimental Setup

- Controller: Ryu with OpenFlow 1.3
- Network emulator: Mininet
- Switches: Open vSwitch
- Traffic generator: iperf3
- Link bandwidth: 100 Mbps
- Bottleneck: 10 Mbps on s2-eth2 (s2 → s4)

Bottleneck configuration:

```bash
tc qdisc replace dev s2-eth2 root tbf rate 10mbit burst 32kbit latency 400ms
```

## 3. Telemetry Configurations

### Experiment A: Prefer s3

```json
{
  "s1-s2-s4": {
    "utilization": 0.90,
    "age_s": 0.1,
    "variability": 0.02
  },
  "s1-s3-s4": {
    "utilization": 0.20,
    "age_s": 0.1,
    "variability": 0.02
  }
}
```

### Experiment B: Prefer s2

```json
{
  "s1-s2-s4": {
    "utilization": 0.20,
    "age_s": 0.1,
    "variability": 0.02
  },
  "s1-s3-s4": {
    "utilization": 0.90,
    "age_s": 0.1,
    "variability": 0.02
  }
}
```

## 4. Results

| Scenario | Selected path | Receiver throughput |
|---|---|---:|
| Normal baseline | s2 | 94.8 Mbps |
| Normal baseline | s3 | 94.7 Mbps |
| s2 bottleneck, telemetry prefers s2 | s2 | 9.54 Mbps |
| s2 bottleneck, telemetry prefers s3 | s3 | 94.7 Mbps |

The results show that the selected path influences the achieved throughput when one path has a configured bandwidth bottleneck.

## 5. OpenFlow Verification

The controller logs and switch flow tables verified forwarding rules on the selected path.

### s3 path

Forward direction:

- s1: port 1 → port 3
- s3: port 1 → port 2
- s4: port 2 → port 3

Reverse direction:

- s4: port 3 → port 2
- s3: port 2 → port 1
- s1: port 3 → port 1

### s2 path

Forward direction:

- s1: port 1 → port 2
- s2: port 1 → port 2
- s4: port 1 → port 3

Reverse direction:

- s4: port 3 → port 1
- s2: port 2 → port 1
- s1: port 2 → port 1

## 6. Interpretation

When telemetry favoured s3, the controller selected the s3 path. Traffic avoided the constrained s2-to-s4 link and achieved approximately 94.7 Mbps receiver throughput.

When telemetry favoured s2, the controller selected the s2 path. The configured 10 Mbps bottleneck reduced receiver throughput to approximately 9.54 Mbps.

The normal-path measurements were approximately equal, as both paths had the same configured link bandwidth and delay.

## 7. Limitations

1. Telemetry values were manually configured in `experiments/telemetry.json`.
2. The controller does not currently collect live switch statistics.
3. The controller does not automatically detect the configured traffic-control bottleneck.
4. Existing flows are not migrated when telemetry changes; path selection occurs for new flows.
5. Throughput measurements were performed in separate runs and may vary due to system and TCP behaviour.

## 8. Software Validation

The Python unit-test suite completed successfully:

```text
9 passed
```

The temporary diagnostic logging used during debugging was subsequently removed. The original forwarding and path-selection implementation was preserved.

## 9. Conclusion

The experiments demonstrate that PathPilot can select between two parallel paths using supplied telemetry and install corresponding forward and reverse OpenFlow rules.

The controlled bottleneck experiment also demonstrates the impact of path selection on achieved throughput. Selecting the unconstrained alternative path allowed traffic to avoid the configured 10 Mbps bottleneck.

These results validate the current prototype's telemetry-driven, per-new-flow path-selection behaviour. They do not demonstrate automatic live congestion detection or dynamic migration of existing flows.