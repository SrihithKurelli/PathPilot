# Professor Rubric Traceability — PathPilot

This document maps the professor's Project Orientation and the revised PathPilot proposal to the current implementation. Statuses distinguish implemented code from measurements that have actually been collected.

## Professor's project orientation

| Expectation | Evidence in repository | Status / remaining work |
|---|---|---|
| Networked software / SDN mechanism | Ryu OpenFlow 1.3 controller, Mininet and OVS topology | Implemented |
| Motivation and appreciation of prior work | Project proposal and literature discussion | Needs a final, cited related-work section and verified bibliography |
| System design | Controller, topology, telemetry, policies and experiment runner | Implemented; add final architecture and sequence diagrams to report |
| Module implementation | Controller, topology, telemetry, policy and experiment modules | Core modules implemented; missing evaluation modules remain |
| End-to-end integration | `.github/workflows/mininet-smoke.yml` runs Ryu + OVS + Mininet, checks connectivity, runs a TCP bottleneck trial and validates ICMP RTT/loss output | Automated Ubuntu CI smoke test passes; repeat the guided demo on the project Ubuntu VM for submission evidence |
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
| Path changes/minute and reversals | Temporal replay plus Mininet selected-path decision logs | Partial: one-trial baseline pilots now validate decision counts, changes and immediate reversals for new-flow decisions; no continuous established-flow churn or changes/minute workload yet |
| Adaptation time and overhead | Ryu-process CPU time, mean CPU percentage and peak RSS are sampled by the Mininet runner | Partial: one-trial pilots completed on both initial paths; no repeated workload study, OVS/host overhead, rule-update latency/counts, telemetry volume or settling-time measurement |
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


## Runtime evaluation instrumentation update

The Mininet single-trial runner now samples the Ryu controller process through Linux `/proc` and records CPU time, mean CPU percentage over the trial, and peak resident memory when the process statistics are available. It also derives path-decision count, path changes, and immediate A→B→A reversals from the controller's selected-path log lines. The balanced matrix aggregator carries these measurements into per-condition/policy summaries.

These are process-level measurements for the controller process only; they do not include child processes, host-wide resource usage, Open vSwitch CPU, or OpenFlow rule-install latency. Path changes are counted across the controller's logged decisions within a trial, not as a continuous path-change rate for established flows.

The helper module also provides a Jain fairness calculation and percentile utility, but the present sequential-flow experiment does not create simultaneous competing TCP flows. Therefore Jain fairness is still **not measured** and no fairness result is emitted. Per-TCP-flow latency distributions and TCP data-plane packet loss also remain unmeasured. The existing ICMP probe remains a separate-flow measurement.

Validation update: the user ran the updated test suite successfully (81 passed) and completed one-trial baseline Mininet pilots for both pinned initial paths (five policies per path, 10 trials total). All topology connectivity checks reported 0% loss and each requested initial path was respected. These pilots validate that the instrumentation runs end-to-end; one repetition per policy/path is not enough for quantitative policy comparisons or overhead conclusions. Audit the generated raw CPU/RSS/path-transition fields and run repeated trials before reporting those metrics.


## Proposal-aligned final harness implementation status (in progress)

The complete implementation contract is recorded in
`docs/FINAL_EVALUATION_IMPLEMENTATION_PLAN.md`. New code now provides:
- deterministic, seed-specific workload definitions for all proposal scenario families;
- TCP application request/echo RTT sampling, separately labelled from ICMP;
- iperf3 TCP/UDP result and interval parsing, with concurrent-window Jain fairness;
- qdisc backlog/drop and OVS port counter sampling;
- structured controller path-decision, FlowMod, and OpenFlow telemetry request/reply event records;
- scheduled path degradation, delay, loss, link-down and recovery command support;
- a per-scenario Mininet trial runner, campaign manifest planner, resumable campaign driver and strict artifact auditor.

This is not yet a completed or validated end-to-end evaluation. The following gates remain before the final campaign:
1. Run the full Python test suite on Python 3.10 and 3.11 and resolve every failure.
2. Validate iperf3 availability and behavior on the Ubuntu VM and inside Mininet hosts.
3. Run a single steady-low rehearsal and inspect TCP application RTT samples, concurrent fairness windows, UDP loss, qdisc/OVS counters, FlowMod counts and telemetry byte estimates.
4. Run burst, mixed-flow, degradation and link-loss recovery smoke tests; verify that impairment commands restore the intended baseline state and cleanup is reliable on failures.
5. Validate adaptation/settling definitions against event and telemetry traces. A utilization threshold is an operational proxy and must be labelled as such; it is not automatically an end-to-end latency recovery result.
6. Add final condition-stratified analysis and plots, verify campaign manifest/result matching, and run the complete integrity auditor.
7. Freeze policy parameters on development workloads before creating the final-test manifest.

The default manifest now uses a balanced fractional design of 2,000 trials: full baseline/delay/noise/combined telemetry coverage for sudden and alternating bursts; baseline+combined for steady low/high, mixed short/long, degradation, link-loss and packet-loss recovery. Both initial paths, all five policies and ten matched repetitions remain represented. The manifest emits a runtime lower-bound estimate. Review the estimate after rehearsal and document any further change before final-test execution.

The event log estimates OpenFlow message bytes when the parsed Ryu message does not retain a serialized wire buffer. These estimates must be reported as estimates, not packet-capture byte counts. Controller CPU/RSS remain process-level and exclude OVS/host-wide overhead. Mininet results remain emulation results.
