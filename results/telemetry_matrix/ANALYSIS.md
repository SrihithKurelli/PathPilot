# Telemetry-Impairment Experiment Analysis

## Executive summary

This analysis interprets the committed 100-trial Mininet telemetry-impairment matrix in `results/telemetry_matrix/`. It uses the per-trial records in `all_conditions_raw.csv`, not just the generated summary table.

**Main result:** the uncertainty-aware policy achieved 100% bottleneck avoidance in all five tested conditions (5/5 trials per condition), with mean second-flow goodput between 85.24 and 85.44 Mbps. The static policy never avoided the bottleneck (0/5 in every condition) and delivered 0.81–1.39 Mbps. Least-loaded and threshold performed well under baseline, delayed-only, and noisy-only conditions, but had mixed results when delay and noise were combined.

These are encouraging results for this particular two-path Mininet setup. They do not establish production-network performance or statistical superiority: each policy-condition cell has only five trials, and the severe/combined cases show high trial-to-trial variability for two policies.

## 1. Experiment scope and method

The topology has two parallel paths between h1 and h2:

- Path 1: `s1-s2-s4`
- Path 2: `s1-s3-s4`

For each trial, the runner starts a fresh Ryu controller and Mininet topology, checks connectivity, starts a first TCP flow, identifies the path chosen for that flow, and applies a 10 Mbps traffic-control bottleneck to that path's second internal link. After telemetry warm-up, it starts a second TCP flow and records the selected path and second-flow goodput while the first flow is still active.

The matrix covers four policies (`static`, `least_loaded`, `threshold`, `uncertainty_aware`) under five conditions:

| Condition | Telemetry delay | Noise standard deviation |
|---|---:|---:|
| baseline | 0 s | 0.00 |
| delayed | 2 s | 0.00 |
| noisy | 0 s | 0.05 |
| combined | 2 s | 0.05 |
| severe_combined | 4 s | 0.10 |

There are five trials per policy per condition: 5 conditions × 4 policies × 5 trials = **100 trials**. The seeds recorded in the CSV are 8–12 for each policy/condition.

### What the measurements mean

- **Second-flow goodput:** TCP throughput of the second flow, in Mbps. This is the primary performance metric because the first flow has already created the bottleneck.
- **Bottleneck avoidance:** whether the second flow was assigned to a path other than the path carrying the first flow and its imposed bottleneck.
- **Connectivity loss:** the Mininet `pingAll()` loss recorded before the two TCP flows.
- **Telemetry evidence:** controller log lines captured immediately before each path decision.

All 100 rows report 0% connectivity loss. For all 100 second-flow decisions, the captured telemetry log says **LIVE telemetry**. The recorded sample age is 0.6 s in baseline/noisy, 2.6 s in delayed/combined, and 4.6 s in severe_combined. For delayed, combined, and severe_combined, the first-flow decision used the static fallback because the historical live sample was not yet available at that initial decision; the second-flow decision—the decision evaluated after the bottleneck warm-up—used live historical telemetry. This distinction matters when describing what the experiment validates.

## 2. Results

Mean and sample standard deviation of second-flow TCP goodput are shown below. Avoidance is the fraction of second flows that did not use the bottlenecked path.

| Condition | Policy | Mean goodput (Mbps) | SD (Mbps) | Avoidance |
|---|---|---:|---:|---:|
| baseline | static | 0.91 | 0.09 | 0% |
| baseline | least_loaded | 85.40 | 0.00 | 100% |
| baseline | threshold | 85.40 | 0.00 | 100% |
| baseline | uncertainty_aware | 85.38 | 0.04 | 100% |
| delayed | static | 0.81 | 0.10 | 0% |
| delayed | least_loaded | 83.72 | 3.65 | 100% |
| delayed | threshold | 85.38 | 0.04 | 100% |
| delayed | uncertainty_aware | 85.34 | 0.06 | 100% |
| noisy | static | 0.82 | 0.11 | 0% |
| noisy | least_loaded | 85.38 | 0.08 | 100% |
| noisy | threshold | 85.42 | 0.04 | 100% |
| noisy | uncertainty_aware | 85.24 | 0.31 | 100% |
| combined | static | 0.99 | 0.09 | 0% |
| combined | least_loaded | 68.42 | 37.76 | 80% |
| combined | threshold | 68.48 | 37.73 | 80% |
| combined | uncertainty_aware | 85.44 | 0.11 | 100% |
| severe_combined | static | 1.39 | 0.33 | 0% |
| severe_combined | least_loaded | 18.05 | 37.65 | 20% |
| severe_combined | threshold | 18.07 | 37.70 | 20% |
| severe_combined | uncertainty_aware | 85.38 | 0.04 | 100% |

The standard deviations are sample standard deviations across five trials. Exact per-trial values, path choices, telemetry logs, and approximate confidence intervals are retained in the raw CSV and generated summary.

## 3. Interpretation by policy

### Static

Static routing always chooses the same lexicographically first path in this implementation. Because the experiment places the bottleneck on the first flow's selected path, the second flow remains on that same path in all 25 static trials. Its goodput stays close to 1 Mbps, and avoidance is 0%.

This is a useful negative-control result: a policy that ignores changing path conditions does not move the new flow away from the induced bottleneck. It is not evidence that static routing always performs poorly in arbitrary topologies or traffic patterns.

### Least-loaded

Least-loaded performs strongly in baseline, delayed-only, and noisy-only conditions, avoiding the bottleneck in all 15 trials across those conditions. Its mean goodput is around 85 Mbps in these cases.

Performance becomes inconsistent when delay and noise are combined. In the combined condition it avoids the bottleneck in 4/5 trials; in severe_combined it avoids it in only 1/5. The corresponding goodput distributions are highly variable: the poor trials are near 1 Mbps, while successful avoidance trials are near 85 Mbps. The means (68.42 and 18.05 Mbps) therefore hide a bimodal outcome and should not be read as typical throughput.

### Threshold

Threshold follows a similar pattern to least-loaded in this experiment: 100% avoidance in baseline, delayed-only, and noisy-only; 80% in combined; and 20% in severe_combined. Its severe and combined means are also mixtures of near-bottleneck and near-uncongested outcomes.

### Uncertainty-aware

Uncertainty-aware avoids the bottleneck in all 25 trials and maintains mean goodput between 85.24 and 85.44 Mbps across all five conditions. This is consistent with the implementation's confidence and noise-margin logic: when the two leading utilization measurements are too close relative to their combined variability, it avoids trusting a small noisy ranking and alternates away from the previously selected path.

This behavior is a heuristic, not a general guarantee that the alternate path is better. It works particularly well in this experiment because the previously selected path is the one on which the first flow's bottleneck is deliberately imposed. A different traffic pattern could make the alternate path congested too.

## 4. Main findings

1. **The experiment distinguishes adaptive path selection from fixed path selection.** Static has 0% bottleneck avoidance; the adaptive policies avoid the bottleneck in most baseline trials.
2. **Delay alone and noise alone were not enough to substantially disrupt least-loaded or threshold in this matrix.** Both achieved 100% avoidance in the separate delayed and noisy conditions.
3. **Combined impairment exposed a weakness in simple utilization ranking.** Least-loaded and threshold each missed the bottleneck in one of five combined trials and four of five severe_combined trials.
4. **The uncertainty-aware heuristic was robust in the tested matrix.** It avoided the bottleneck in every trial, including severe_combined.
5. **Connectivity remained intact.** All trials recorded 0% ping loss; the observed differences are path-choice/goodput effects, not a connectivity failure.

## 5. Limitations and threats to validity

- **Small sample size:** five trials per policy-condition cell is a pilot-sized evaluation. A single trial changes the avoidance rate by 20 percentage points.
- **Approximate intervals:** the existing summary uses normal-approximation 95% intervals. With n=5, these are not reliable substitutes for a larger-sample or appropriately modeled analysis. They are especially misleading for the bimodal combined/severe results.
- **One topology and one bottleneck pattern:** there are two paths and one 10 Mbps bottleneck imposed on the first flow's chosen path. This does not cover multiple simultaneous bottlenecks, asymmetric capacity, cross traffic, or more than two candidate paths.
- **One traffic workload:** the primary metric is second-flow TCP goodput while the first TCP flow remains active. It does not measure UDP behavior, mixed workloads, fairness, tail latency, or long-term flow churn.
- **No migration:** the controller selects paths for new flows; established flows are not moved after conditions change.
- **Controlled impairment model:** Gaussian noise and historical-sample delay are useful controlled perturbations, but they do not represent every failure mode of real switch counters, controller scheduling, or telemetry transport.
- **Emulation only:** Mininet/OVS results are not measurements from physical switches or a production network.
- **First-decision fallback:** in delayed and combined conditions, the first flow's selection used static fallback telemetry, while the second flow's selection used live historical telemetry. The primary second-flow decision is therefore tested under the configured delay/noise, but the initial path is not selected from delayed live telemetry in those trials.

## 6. Recommended next experiments

Prioritize these before claiming general robustness:

1. **Increase repetitions:** run at least 20–30 trials per policy-condition, retaining every raw row and recording failures rather than silently dropping them.
2. **Repeat with reversed bottleneck placement:** explicitly test both path 1 and path 2 as the initially selected/bottlenecked path, to ensure the result is not tied to path ordering or fallback behavior.
3. **Add load patterns:** test both paths partially loaded, both paths congested, different bottleneck rates (e.g. 5, 10, 20 Mbps), and background cross traffic.
4. **Test impairment sweeps:** vary delay and noise independently over more levels, then use a grid to identify where each policy degrades.
5. **Measure additional metrics:** add packet loss during traffic, per-flow fairness, latency (including tail latency), controller CPU, decision time, and OpenFlow rule/flow counts.
6. **Use stronger statistical reporting:** report per-trial scatter/box plots and medians/IQR; use bootstrap or suitable small-sample intervals, and avoid relying on means for the visibly bimodal cells.

## 7. Reproduction

From the repository root on the Ubuntu Mininet VM:

```bash
sudo env PYTHONPATH=/home/pathpilot/PathPilot \
  /usr/bin/python3 experiments/run_telemetry_matrix.py --dry-run
```

The committed dataset was produced with five trials per policy per condition. To reproduce a fresh five-trial run:

```bash
sudo env PYTHONPATH=/home/pathpilot/PathPilot \
  /usr/bin/python3 experiments/run_telemetry_matrix.py --trials 5
```

The run writes the per-condition CSV files and regenerates the aggregate report. Keep the resulting raw CSVs and software revision together. A fresh run may differ slightly because Mininet and TCP measurements are timing-sensitive.

## 8. Artifacts

- Raw trials: [`all_conditions_raw.csv`](all_conditions_raw.csv)
- Per-condition raw files: `baseline_raw.csv`, `delayed_raw.csv`, `noisy_raw.csv`, `combined_raw.csv`, `severe_combined_raw.csv`
- Generated summary: [`summary.csv`](summary.csv)
- Original generated results table: [`REPORT.md`](REPORT.md)
- Runner: [`../../experiments/run_telemetry_matrix.py`](../../experiments/run_telemetry_matrix.py)

