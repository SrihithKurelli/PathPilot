# PathPilot — 500-trial balanced Mininet evaluation analysis

## Scope and provenance

This analysis was generated from the supplied `all_balanced_raw.csv`, `balanced_summary.csv`, and `BALANCED_REPORT.md`. It is descriptive analysis of Mininet/Open vSwitch emulation, not a physical-network benchmark.

- Trials: 500
- Unique trial keys: 500
- Duplicate trial keys: 0
- Successive policy-selected TCP measurements: 2,000
- Policies: static, least_loaded, threshold, stability_aware, uncertainty_aware
- Conditions: baseline, delayed, noisy, combined, severe_combined
- Initial bottleneck placements: `s1-s2-s4` and `s1-s3-s4`
- Recorded Git revision: `c2d8588c2346e17880e669a9990ea8873bf67c98`
- Dirty-tree rows: 0

## Integrity audit

| Check | Result |
|---|---:|
| Rows | 500 |
| Unique trial keys | 500 |
| Duplicate keys | 0 |
| Rows with malformed successive-flow arrays | 0 |
| Successive-flow records | 2,000 |
| Nonzero successive-flow client return codes | 0 |
| Nonzero first-flow client return codes | 0 |
| Nonzero second-flow client return codes | 0 |
| Nonzero ICMP probe return codes | 0 |
| Trials with connectivity loss | 0 |
| Trials with ICMP probe loss | 0 |

## Successive-flow fallback audit

For uncertainty-aware policy:
- Fallback invocations: 298 / 400 successive decisions.
- Fallback path counts: `s1-s2-s4: 159`, `s1-s3-s4: 139`.
- Trials with all four decisions falling back: 60.
- Trials with a mixture of fallback and confidence-qualified decisions: 39.
- Trials with no fallback: 1.

The audit classifies only reason strings beginning with `Uncertainty fallback:` as fallback invocations; `NO_FALLBACK_USED` is explicitly excluded. These checks establish that the low-confidence fallback was invoked and that its choices were distributed across the two paths. They do not establish that it detected which path was uncongested. Round-robin is a distribution mechanism, not a congestion estimator.

## Main interpretation

1. **Keep the two initial bottleneck placements separate.** Static always chooses Path 1; therefore its result changes sharply when the bottleneck placement changes. Pooling placements can hide this structural effect.
2. **First policy-selected flow and four-flow aggregate are different estimands.** The first policy-selected flow is the legacy second-flow measurement after a test-pinned priming flow. Successive-flow metrics pool four separately measured new TCP flows within one controller process.
3. **Uncertainty-aware routing is not uniformly best.** In the Path 1 bottleneck placement, its first policy-flow avoidance falls to zero in combined, delayed and severe-combined conditions, while least-loaded/threshold retain higher first-flow avoidance in several of those cells. The fallback can improve aggregate successive-flow distribution, but it cannot be described as reliably identifying the uncongested path.
4. **Baseline is strong for adaptive policies on the first decision.** Under baseline telemetry, most adaptive policies avoid the bottleneck. Successive-flow results are more variable and should be read separately.
5. **No connectivity or ICMP probe loss was recorded.** This does not imply zero TCP data-plane packet loss; that metric was not instrumented independently.
6. **ICMP p99 is a separate probe-flow RTT percentile.** It is not a per-TCP-flow latency percentile and must not be reported as TCP p99.

## Figures

The accompanying analysis bundle contains:
- `first_flow_avoidance.png`: bottleneck avoidance for the first policy-selected TCP flow.
- `successive_flow_avoidance.png`: pooled avoidance across four successive policy-selected flows per trial.
- `successive_goodput.png`: mean goodput across those successive flows.
- `icmp_probe_p99.png`: separate ICMP probe p99 under concurrent TCP load.

## Metrics still not established

The supplied data does not measure:
- per-TCP-flow p50/p95/p99 latency;
- TCP data-plane packet loss;
- Jain fairness across simultaneous competing flows;
- controller CPU and memory overhead;
- flow-rule update counts/latency;
- live Mininet path changes/reversals over time under a concurrent workload;
- adaptation/settling time;
- queue occupancy or queue-drop telemetry;
- bursty and mixed-duration packet-level Mininet workloads;
- link failure and recovery behavior.

These should either be implemented and measured before making claims, or explicitly marked out of scope in the final report. Do not infer them from throughput or ICMP probe measurements.

## Reproducibility

The raw data and original generated report supplied for this analysis should be preserved unchanged. This committed analysis adds the verified audit and interpretation; it does not replace the raw CSVs or original report. The full derived tables, long-form successive-flow CSV and figures are provided in the downloadable analysis bundle.
