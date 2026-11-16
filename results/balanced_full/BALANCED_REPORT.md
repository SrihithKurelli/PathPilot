# Counterbalanced Initial-Path Mininet Results

- Conditions included: 5 (baseline, combined, delayed, noisy, severe_combined)
- Initial bottleneck paths: s1-s2-s4, s1-s3-s4
- Policies: static, least_loaded, threshold, uncertainty_aware
- Total Mininet trials represented: 400
- Primary metric: second-flow TCP goodput (Mbps)
- Dispersion: median and inclusive interquartile range (Q1–Q3)

| Condition | Initial/bottleneck path | Policy | n | Mean Mbps | Median Mbps | Q1–Q3 Mbps | Avoidance |
|---|---|---|---:|---:|---:|---:|---:|
| baseline | s1-s2-s4 | least_loaded | 10 | 85.39 | 85.40 | 85.33–85.40 | 100% |
| baseline | s1-s2-s4 | static | 10 | 0.87 | 0.87 | 0.86–0.95 | 0% |
| baseline | s1-s2-s4 | threshold | 10 | 84.54 | 85.40 | 85.30–85.40 | 100% |
| baseline | s1-s2-s4 | uncertainty_aware | 10 | 84.56 | 85.40 | 85.40–85.40 | 100% |
| baseline | s1-s3-s4 | least_loaded | 10 | 85.39 | 85.40 | 85.40–85.40 | 100% |
| baseline | s1-s3-s4 | static | 10 | 85.36 | 85.40 | 85.30–85.40 | 100% |
| baseline | s1-s3-s4 | threshold | 10 | 84.87 | 84.80 | 84.80–84.90 | 100% |
| baseline | s1-s3-s4 | uncertainty_aware | 10 | 84.88 | 84.90 | 84.83–84.90 | 100% |
| combined | s1-s2-s4 | least_loaded | 10 | 76.84 | 85.35 | 85.30–85.40 | 90% |
| combined | s1-s2-s4 | static | 10 | 0.84 | 0.85 | 0.84–0.86 | 0% |
| combined | s1-s2-s4 | threshold | 10 | 76.91 | 85.35 | 85.30–85.40 | 90% |
| combined | s1-s2-s4 | uncertainty_aware | 10 | 75.84 | 84.90 | 84.80–85.22 | 90% |
| combined | s1-s3-s4 | least_loaded | 10 | 85.28 | 85.40 | 85.30–85.40 | 100% |
| combined | s1-s3-s4 | static | 10 | 85.25 | 85.35 | 85.30–85.40 | 100% |
| combined | s1-s3-s4 | threshold | 10 | 85.11 | 85.15 | 84.83–85.40 | 100% |
| combined | s1-s3-s4 | uncertainty_aware | 10 | 84.31 | 85.35 | 84.83–85.40 | 100% |
| delayed | s1-s2-s4 | least_loaded | 10 | 85.11 | 85.10 | 84.90–85.38 | 100% |
| delayed | s1-s2-s4 | static | 10 | 0.92 | 0.88 | 0.86–0.98 | 0% |
| delayed | s1-s2-s4 | threshold | 10 | 84.53 | 85.40 | 85.30–85.40 | 100% |
| delayed | s1-s2-s4 | uncertainty_aware | 10 | 85.32 | 85.30 | 85.20–85.40 | 100% |
| delayed | s1-s3-s4 | least_loaded | 10 | 85.37 | 85.40 | 85.30–85.47 | 100% |
| delayed | s1-s3-s4 | static | 10 | 84.56 | 85.40 | 85.33–85.47 | 100% |
| delayed | s1-s3-s4 | threshold | 10 | 85.18 | 85.35 | 84.92–85.40 | 100% |
| delayed | s1-s3-s4 | uncertainty_aware | 10 | 84.91 | 84.90 | 84.80–84.90 | 100% |
| noisy | s1-s2-s4 | least_loaded | 10 | 85.24 | 85.25 | 85.05–85.40 | 100% |
| noisy | s1-s2-s4 | static | 10 | 0.92 | 0.89 | 0.86–1.00 | 0% |
| noisy | s1-s2-s4 | threshold | 10 | 85.36 | 85.35 | 85.30–85.40 | 100% |
| noisy | s1-s2-s4 | uncertainty_aware | 10 | 85.38 | 85.40 | 85.40–85.40 | 100% |
| noisy | s1-s3-s4 | least_loaded | 10 | 85.37 | 85.40 | 85.30–85.40 | 100% |
| noisy | s1-s3-s4 | static | 10 | 85.04 | 84.95 | 84.83–85.33 | 100% |
| noisy | s1-s3-s4 | threshold | 10 | 85.38 | 85.40 | 85.40–85.40 | 100% |
| noisy | s1-s3-s4 | uncertainty_aware | 10 | 85.39 | 85.40 | 85.33–85.40 | 100% |
| severe_combined | s1-s2-s4 | least_loaded | 10 | 26.64 | 1.24 | 1.23–64.57 | 30% |
| severe_combined | s1-s2-s4 | static | 10 | 1.33 | 1.23 | 1.21–1.24 | 0% |
| severe_combined | s1-s2-s4 | threshold | 10 | 26.67 | 1.25 | 1.23–64.80 | 30% |
| severe_combined | s1-s2-s4 | uncertainty_aware | 10 | 26.19 | 1.22 | 1.19–62.86 | 30% |
| severe_combined | s1-s3-s4 | least_loaded | 10 | 59.47 | 84.70 | 21.35–84.88 | 100% |
| severe_combined | s1-s3-s4 | static | 10 | 65.90 | 83.30 | 76.38–84.78 | 100% |
| severe_combined | s1-s3-s4 | threshold | 10 | 76.90 | 85.40 | 85.33–85.47 | 100% |
| severe_combined | s1-s3-s4 | uncertainty_aware | 10 | 85.55 | 85.50 | 85.40–85.50 | 100% |

## Interpretation and validity

- Compare policies within the same condition and initial path before combining path placements.
- The first flow is pinned by a test-only controller setting; it does not update the controller's previous-policy-path state.
- The second flow is selected by the configured routing policy using the controller's telemetry and normal policy logic.
- Avoidance means the second flow used a path other than the independently pinned, bottlenecked initial path.
- Both initial paths are represented separately so path-order effects remain visible.
- These are Mininet/OVS emulation results, not physical-network or production measurements.
- The experiment measures TCP goodput and path choice; it does not measure p99 latency, fairness, or controller CPU.
- The first pinned flow does not consume a telemetry sample or update the policy's previous-path state; first-flow telemetry fields explicitly record that pin.
- All raw trial rows and controller log evidence are retained in the cell CSVs and combined CSV.
