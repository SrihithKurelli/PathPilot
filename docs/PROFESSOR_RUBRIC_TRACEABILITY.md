# Professor Rubric Traceability — PathPilot

This document maps the professor's Project Orientation and the revised PathPilot proposal to the current implementation. Statuses distinguish implemented code from measurements that have actually been collected.

## Professor's project orientation

| Expectation | Evidence in repository | Status / remaining work |
|---|---|---|
| Networked software / SDN mechanism | Ryu OpenFlow 1.3 controller, Mininet and OVS topology | Implemented |
| Motivation and appreciation of prior work | Project proposal and literature discussion | Needs a final, cited related-work section and verified bibliography |
| System design | Controller, topology, telemetry, policies and experiment runner | Implemented; add final architecture and sequence diagrams to report |
| Module implementation | Controller, topology, telemetry, policy and experiment modules | Core modules implemented; missing evaluation modules remain |
| End-to-end integration | Mininet + OVS + Ryu experiment runner | Previously exercised; rerun a clean end-to-end demo before final submission |
| Performance evaluation | 400-trial counterbalanced Mininet matrix and synthetic replay | Partial: goodput/path avoidance measured; proposal's full metrics/scenarios not covered |
| Near-real-world deployment / demo | Mininet + OVS + Ryu | Suitable emulated deployment; prepare a one-command guided demo and evidence bundle |
| References | README/proposal literature notes | Final report must include complete references and careful novelty claims |

## Revised proposal implementation and evaluation

| Requirement | Current evidence | Status |
|---|---|---|
| Multi-path Mininet/OVS topology | `topology/mininet_topology.py` | Implemented: two parallel paths |
| Configurable capacity, delay, loss and bottlenecks | Topology TCLink settings and experiment TBF bottleneck | Partial: bottleneck and fixed link delay/capacity exist; generalized loss/failure controls need implementation |
| Utilization telemetry | `controller/live_telemetry.py` from OpenFlow tx-byte counters | Implemented |
| Queue/drop counters | No live queue/drop telemetry collector yet | Missing |
| End-to-end latency | No latency distribution collector in current Mininet runner | Missing |
| Sampling delay and noise | Ryu environment controls and historical telemetry | Implemented |
| Static, least-loaded, threshold baselines | `controller/policies.py` | Implemented |
| Stability-aware baseline | `controller/policies.py` (`stability_aware`) and policy tests | Implemented as a fixed 0.10 absolute-utilization hysteresis comparator; not a novel contribution |
| Confidence-aware new-flow placement | `uncertainty_aware` policy | Implemented as a heuristic; not a proven research contribution |
| Existing flows remain on selected paths | Installed per-flow OpenFlow rules; no migration logic | Implemented for prototype |
| Reproducible experiment runner | Balanced Mininet matrix, seeds, raw CSV and controller logs | Implemented for existing goodput/path-choice experiments |
| Steady low/high, burst and alternating-burst workloads | `experiments/policy_replay.py` deterministic synthetic scenarios | Partial: policy-level simulation exists; corresponding traffic workloads still need Mininet execution |
| Mixed short/long flows | Synthetic aggregate-load proxy in `experiments/policy_replay.py` | Partial: not a packet-level mixed-flow experiment |
| Telemetry impairment | 5 conditions in 400-trial matrix | Implemented |
| Path degradation/link loss and recovery | Bottleneck experiment only | Partial |
| Primary p99 end-to-end latency | Mininet runner now records concurrent ICMP probe RTT p50/p95/p99 | Partial: ICMP probe is a separate flow; TCP-flow latency distributions are not measured |
| Goodput and packet loss | TCP goodput plus concurrent ICMP probe packet loss; initial connectivity ping loss | Partial: ICMP loss is not TCP data-plane packet loss |
| Jain fairness | Not measured | Missing |
| Path changes/minute and reversals | Temporal replay emits changes/minute and reversal counts; `experiments/analyze_results.py` summarizes them | Partial: synthetic replay metrics only; Mininet/controller runtime metrics remain unmeasured |
| Adaptation time and overhead | Not measured systematically | Missing |
| Fixed seeds, repeated trials and raw data | 400-trial matrix and raw CSV archive | Implemented for existing conditions |

## Work required before claiming rubric completion

1. Add deterministic traffic scenarios: steady low/high, burst/alternating burst, mixed short/long flows, degradation and recovery.
2. Extend the experiment harness to collect latency distributions (including p99), packet loss, per-flow goodput/fairness, path changes/reversals, controller CPU, rule updates and telemetry volume.
3. Add configurable link impairment/failure controls and verify recovery behavior.
4. Run the new scenarios on the Ubuntu Mininet VM; code inspection and CI alone cannot establish live deployment success.
5. Produce the final report, plots, run manifest, demo recording/screenshots and full references.

## Claim discipline

- Existing 400-trial results are Mininet/OVS emulation results, not physical-network measurements.
- The current measured primary outcome is second-flow TCP goodput and bottleneck avoidance, not p99 latency.
- The uncertainty-aware policy is a heuristic using sample age and variability. Do not claim novelty or statistically robust uncertainty estimation without a literature audit and suitable evidence.
- Do not claim the rubric is fully satisfied until the missing experiments are run and independently checked.
