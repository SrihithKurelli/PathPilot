# PathPilot: 400-Trial Balanced Mininet Experiment Analysis

## Experiment design

The balanced experiment evaluates four routing policies under five telemetry conditions, with the bottleneck deliberately placed on each of the two candidate paths in separate cells.

- Policies: `static`, `least_loaded`, `threshold`, `uncertainty_aware`
- Conditions: baseline, delayed, noisy, combined, severe combined
- Initial/bottleneck paths: `s1-s2-s4` (Path 1), `s1-s3-s4` (Path 2)
- Repetitions: 10 per policy/condition/path cell
- Total: 5 × 2 × 4 × 10 = **400 trials**
- Primary metric: second-flow TCP goodput (Mbps)
- Avoidance: second flow selects a path other than the path pinned for the first flow
- Connectivity loss: 0% across the 400 trials

The first flow is pinned only to establish the controlled bottleneck. The second flow is selected by the routing policy. The 24-trial iperf diagnostic run conducted separately is not included in these 400 observations.

## Main findings

### Path 1 bottlenecked (`s1-s2-s4`)

| Telemetry condition | Least-loaded avoidance | Threshold avoidance | Uncertainty-aware avoidance |
|---|---:|---:|---:|
| Baseline | 100% | 100% | 100% |
| Delayed | 100% | 100% | 100% |
| Noisy | 100% | 100% | 100% |
| Combined | 90% | 90% | 90% |
| Severe combined | 30% | 30% | 30% |

Static routing always selects Path 1, so it does not avoid the bottleneck in these Path 1-bottlenecked cells.

The adaptive policies perform strongly with baseline, delayed, and noisy telemetry individually. Their avoidance rate drops under combined impairment and falls to 30% under severe combined delay and noise. This is evidence that simultaneous severe telemetry delay and noise can mislead the path-selection decisions in this emulated setup.

The severe-combined throughput distributions are highly dispersed/bimodal. For example, with Path 1 bottlenecked, least-loaded has mean second-flow goodput of 26.64 Mbps but median 1.24 Mbps. The mean is lifted by the minority of trials that avoid the bottleneck; it does not represent the typical trial.

### Path 2 bottlenecked (`s1-s3-s4`)

Static routing selects Path 1, which is the unbottlenecked alternative in this placement. Consequently, static routing can perform well here. All policies recorded 100% bottleneck avoidance in the Path 2-bottlenecked cells.

There are nevertheless severe-combined throughput anomalies: six trials recorded second-flow goodput below 1 Mbps even though the alternate path was selected and `avoided_bottleneck` was true. Some corresponding first-flow rates were also unusually low. The raw CSV does not establish the cause. These observations should be described as anomalous Mininet/traffic outcomes, not as proof that the path-selection decision was incorrect.

## Telemetry and connectivity checks

- The experiment's second-flow decisions used live telemetry in the recorded rows.
- Recorded telemetry age increases with the configured delay (approximately 0.6 s baseline, 2.6 s delayed/combined, and 4.6 s severe combined).
- Connectivity loss was zero in all trials. The observed failures concern throughput and path selection, not reachability.

## Interpretation and limitations

1. Compare policies within the same telemetry condition and initial/bottleneck path. The two placements are not interchangeable because static routing always selects Path 1.
2. Each cell has only 10 repetitions. Report medians, quartiles, standard deviations, and trial-level spread alongside means.
3. Do not claim statistical significance from these descriptive results alone.
4. The uncertainty-aware policy is a heuristic variant; this experiment does not establish it as a statistically optimal estimator.
5. These are Mininet/Open vSwitch emulation results on a two-path topology with a controlled bottleneck, not measurements from a physical or production network.
6. The primary metric is second-flow TCP goodput. The experiment does not establish tail latency, fairness, controller CPU overhead, or behavior on larger topologies.
7. The cause of the low-throughput severe-combined Path 2 anomalies is not established by the CSV.

## Conclusion

PathPilot demonstrates that telemetry-driven path selection can avoid a controlled congested path and maintain high second-flow TCP goodput when telemetry is fresh or moderately impaired. The experiment also identifies a clear limitation: when telemetry delay and noise are simultaneously severe, the adaptive policies can make incorrect routing decisions. Improving stale/noisy telemetry handling and repeating severe-condition experiments with more repetitions and additional instrumentation are useful next steps.

## Reproducibility

The raw 400-trial CSV and generated cell/summary files should be kept alongside this analysis under `results/balanced_full/`. The experiment runner is:

```bash
sudo env PYTHONPATH=/home/pathpilot/PathPilot \
  /usr/bin/python3 experiments/run_balanced_path_matrix.py \
  --trials 10 --output-dir results/balanced_full
```

The run is already complete; this command is included for reproducibility only and should not be rerun merely to publish the existing results.
