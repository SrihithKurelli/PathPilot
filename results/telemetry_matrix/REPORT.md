# Controlled Telemetry-Impairment Mininet Results

- Trials per policy per condition: 5
- Policies: static, least_loaded, threshold, uncertainty_aware
- Conditions included: 5 (baseline, combined, delayed, noisy, severe_combined)
- Total Mininet trials represented: 100
- Metric: second-flow TCP goodput (Mbps)
- Confidence intervals: approximate normal 95% intervals

| Condition | Delay (s) | Noise std | Policy | n | Mean Mbps | SD | Avoidance | Connectivity loss |
|---|---:|---:|---|---:|---:|---:|---:|---:|
| baseline | 0.0 | 0.00 | least_loaded | 5 | 85.40 | 0.00 | 100% | 0.00% |
| baseline | 0.0 | 0.00 | static | 5 | 0.91 | 0.09 | 0% | 0.00% |
| baseline | 0.0 | 0.00 | threshold | 5 | 85.40 | 0.00 | 100% | 0.00% |
| baseline | 0.0 | 0.00 | uncertainty_aware | 5 | 85.38 | 0.04 | 100% | 0.00% |
| combined | 2.0 | 0.05 | least_loaded | 5 | 68.41 | 37.76 | 80% | 0.00% |
| combined | 2.0 | 0.05 | static | 5 | 0.98 | 0.09 | 0% | 0.00% |
| combined | 2.0 | 0.05 | threshold | 5 | 68.48 | 37.73 | 80% | 0.00% |
| combined | 2.0 | 0.05 | uncertainty_aware | 5 | 85.44 | 0.11 | 100% | 0.00% |
| delayed | 2.0 | 0.00 | least_loaded | 5 | 83.72 | 3.65 | 100% | 0.00% |
| delayed | 2.0 | 0.00 | static | 5 | 0.81 | 0.10 | 0% | 0.00% |
| delayed | 2.0 | 0.00 | threshold | 5 | 85.38 | 0.04 | 100% | 0.00% |
| delayed | 2.0 | 0.00 | uncertainty_aware | 5 | 85.34 | 0.05 | 100% | 0.00% |
| noisy | 0.0 | 0.05 | least_loaded | 5 | 85.38 | 0.08 | 100% | 0.00% |
| noisy | 0.0 | 0.05 | static | 5 | 0.82 | 0.11 | 0% | 0.00% |
| noisy | 0.0 | 0.05 | threshold | 5 | 85.42 | 0.04 | 100% | 0.00% |
| noisy | 0.0 | 0.05 | uncertainty_aware | 5 | 85.24 | 0.31 | 100% | 0.00% |
| severe_combined | 4.0 | 0.10 | least_loaded | 5 | 18.05 | 37.65 | 20% | 0.00% |
| severe_combined | 4.0 | 0.10 | static | 5 | 1.39 | 0.33 | 0% | 0.00% |
| severe_combined | 4.0 | 0.10 | threshold | 5 | 18.07 | 37.69 | 20% | 0.00% |
| severe_combined | 4.0 | 0.10 | uncertainty_aware | 5 | 85.38 | 0.04 | 100% | 0.00% |

## Interpretation notes

- Compare policies within the same condition; compare conditions to assess impairment sensitivity.
- A trial is valid only if the runner completes its connectivity check and records both flow decisions and goodput.
- The avoidance rate is the fraction of second flows assigned to a path other than the bottlenecked first-flow path.
- These are Mininet emulation results, not production-network measurements.
- The experiment measures TCP goodput and path choice; it does not measure p99 latency, fairness, or controller CPU.
- Noise standard deviation is applied to normalized utilization; 0.05 corresponds to five percentage points before clipping.
- Delayed samples are historical telemetry samples, not merely an altered age label.
- The 4-second/0.10 severe condition is a stress case and may cause fallback behavior; report failures rather than silently omitting them.

Raw per-condition CSV files and the combined raw CSV are stored alongside this report.
