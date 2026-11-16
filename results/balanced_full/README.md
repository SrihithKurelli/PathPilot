# Balanced 400-trial experiment archive

This folder contains the completed balanced Mininet experiment. It is archived for inspection and reproducibility; **do not rerun the 400 trials just to view these results**.

## Start here

1. [Detailed analysis](ANALYSIS.md) — findings, interpretation, anomalies, limitations, and conclusion.
2. [Generated experiment report](BALANCED_REPORT.md) — all 40 condition/path/policy summary rows.
3. [Combined raw data](all_balanced_raw.csv) — all 400 trial records, including telemetry and iperf diagnostics.
4. [Recomputed summary](balanced_summary.csv) — grouped descriptive statistics.

## Raw data layout

The experiment is a balanced factorial matrix:

- 5 telemetry conditions: baseline, delayed, noisy, combined, severe_combined
- 2 initial/bottleneck paths: `s1-s2-s4` and `s1-s3-s4`
- 4 policies: static, least_loaded, threshold, uncertainty_aware
- 10 repetitions per cell
- 40 cells × 10 trials = 400 rows

Each `<condition>_<path>_raw.csv` file contains one cell. The combined CSV contains the same trial records in one file. Use the combined CSV for analysis across cells; use the individual files to inspect or rerun calculations for a specific cell.

## Recommended review order

1. Read the experiment design and limitations in [ANALYSIS.md](ANALYSIS.md).
2. Inspect the 40-row grouped table in [BALANCED_REPORT.md](BALANCED_REPORT.md).
3. Check the corresponding ten raw rows for any result you want to discuss.
4. Compare the two bottleneck placements separately before drawing conclusions.

## Important interpretation cautions

- Static routing always chooses Path 1. Its result therefore depends directly on which path was bottlenecked.
- Bottleneck avoidance records whether the second flow selected a path other than the pinned first-flow path. It is a path-choice metric, not itself a throughput metric.
- Severe-combined results can be highly dispersed; report medians and quartiles alongside means.
- Six severe-combined trials with Path 2 bottlenecked show sub-1 Mbps second-flow throughput despite recorded avoidance. The raw data does not establish the cause.
- The 24-trial follow-up iperf diagnostic run is separate and is not included in this archive.
- These are Mininet/Open vSwitch emulation results, not physical or production network measurements. The study does not establish tail latency, fairness, controller CPU overhead, or statistical significance.

## Reproduction

The original run used:

```bash
sudo env PYTHONPATH=/home/pathpilot/PathPilot \
  /usr/bin/python3 experiments/run_balanced_path_matrix.py \
  --trials 10 --output-dir results/balanced_full
```

This command is provided as provenance only. The completed raw data is already committed here.
