# PathPilot Experimental Results

## 1. Synthetic Policy Replay

The synthetic replay evaluated four policies across six scenarios:
balanced, changing_load, noisy_telemetry, path1_hot, path2_hot,
and stale_telemetry.

- Total decisions: 24,000
- Policies: static, least_loaded, threshold, uncertainty_aware
- Decisions per scenario-policy combination: 1,000

The least-loaded, threshold, and uncertainty-aware policies performed
well under changing load and path-specific congestion.

Static routing performed poorly when the initially selected path
became congested.

Under noisy telemetry, static routing had lower mean regret than
least-loaded routing in this particular simulation.

The stale_telemetry scenario selected the oracle-best fallback path.
This outcome should not be interpreted as evidence that stale
telemetry is generally harmless.

Detailed results: policy_summary.csv
Raw decisions: policy_replay.csv

## 2. Mininet Policy Evaluation

The Mininet evaluation used a two-path topology with a 100 Mbps
link capacity. A 10 Mbps TBF bottleneck was applied to the first
flow's selected path. A second flow was then established to evaluate
whether the routing policy avoided the bottleneck.

Each policy was evaluated over 10 trials.

| Policy | Mean second-flow throughput (Mbps) | Bottleneck avoidance |
|---|---:|---:|
| Static | 0.8816 | 0% |
| Least-loaded | 84.66 | 100% |
| Threshold | 85.28 | 100% |
| Uncertainty-aware | 85.26 | 100% |

Static routing repeatedly selected the congested path, resulting
in approximately 0.88 Mbps mean throughput for the second flow.

The telemetry-driven policies avoided the bottleneck in all 10
trials and achieved approximately 84.7–85.3 Mbps.

Connectivity loss was 0% in the recorded trials.

Detailed summary: mininet_policy_summary.csv
Raw 10-trial measurements: mininet_policy_results_10.csv

## 3. Interpretation

The Mininet experiment demonstrates that live telemetry-based
selection can improve throughput when one path becomes congested.

The synthetic replay provides additional controlled comparisons
across changing load, noise, and stale telemetry scenarios.

These are separate experiments and should not be combined into
a single performance metric.

## 4. Limitations

- Synthetic replay is a simulation, not a physical network measurement.
- Mininet results represent the configured topology and traffic conditions.
- The Mininet evaluation measures TCP throughput and path selection.
- These experiments do not establish performance under every real-world
  telemetry failure, topology, or traffic pattern.
- The reported confidence intervals are approximate.

