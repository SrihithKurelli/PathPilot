# PathPilot final evaluation implementation plan

This plan operationalizes the Revised Project Proposal. It is the contract for implementation and the final campaign. The campaign must not start until every required metric has a validated source, tests pass, and the manifest/schema are frozen.

## Research question

Under bursty traffic and delayed or noisy telemetry, does uncertainty-aware placement of new flows improve p99 end-to-end latency and reduce unnecessary route changes versus least-loaded, threshold, and stability-aware routing, without unacceptable goodput or fairness regressions?

The uncertainty-aware policy is a candidate extension, not a verified literature gap. Generic hysteresis, route-change penalties, smoothing, and stability metrics are not novelty claims. Compare against HAASP and related systems before making novelty claims.

## Required topology and impairment controls

- Mininet/Open vSwitch multi-path topology.
- Per-link capacity and delay configuration.
- Configurable packet loss.
- Configurable bottleneck rate and bottleneck placement.
- Link degradation/down/recovery events with timestamps.
- Record actual applied qdisc/link state and command output in the raw evidence.

## Required workloads

Every policy receives identical offered traffic and deterministic workload seeds within a matched trial block.

1. Steady low load.
2. Steady high load.
3. Sudden bursts.
4. Alternating bursts between paths / load phases.
5. Mixed short and long TCP flows.
6. UDP load profiles alongside TCP flows.
7. Telemetry delay.
8. Telemetry measurement noise.
9. Path degradation, link loss, and recovery.

Use development scenarios for tuning. Freeze policy parameters before final test workloads. The final test matrix must not be used to tune thresholds.

## Metrics and operational definitions

| Metric | Operational definition | Source / caveat |
|---|---|---|
| Primary p99 end-to-end latency | p99 of per-packet/per-request TCP application RTT samples at a fixed offered load; report per-flow and aggregate | Use TCP timestamp/sequence instrumentation or a validated application-level probe. ICMP p99 is a separate diagnostic and must never be labelled TCP p99. |
| Goodput | Delivered application payload bits / measurement interval, per flow and aggregate | iperf3 JSON or equivalent; retain interval and sender/receiver evidence. |
| Packet loss | UDP sequence-number loss and/or measured qdisc/OVS drop counters; report each source separately | TCP retransmissions are diagnostic, not an exact packet-loss percentage. |
| Fairness | Jain index over simultaneous competing flows' delivered goodput during the same measurement window | Do not calculate from sequential flows. |
| Routing stability | New-flow path decisions, changes/minute, and A→B→A reversals within a predeclared window | Existing flows are pinned; this is decision stability, not established-flow migration. |
| Adaptation / settling | Time from impairment event to first stable policy state meeting a predeclared utilization/latency criterion for a continuous hold interval | Store event timestamps and raw telemetry/decisions; define threshold and hold interval before final run. |
| Controller CPU | Ryu process CPU seconds and normalized mean/peak CPU | Keep separate from host and OVS CPU. |
| Memory | Ryu process peak RSS | Process-level only. |
| Rule updates | Count FlowMod add/modify/delete messages and record timestamps; derive update rate and decision-to-install delay | Instrument controller send path; count only successfully submitted messages and distinguish adds/deletes. |
| Telemetry volume | OpenFlow stats request/reply counts and bytes, plus sampling frequency | Count request/reply messages and serialized payload estimates; state what byte count represents. |
| Utilization | Per-link transmit/receive rate and normalized utilization | Preserve raw counters, sample timestamps, capacity, age, and noise injection. |
| Queue/drop | Queue occupancy where supported, qdisc backlog/drops/overlimits, OVS port/interface drops | Report unavailable counters as unavailable, not zero. |
| Control-plane decision evidence | Chosen path, policy, confidence, age, variability, fallback reason, prior path, and decision timestamp | One structured record per new-flow decision. |

## Experimental controls and reporting

- Fixed topology, software versions, policy version, traffic profile, offered load, and workload seeds.
- Matched seeds across policies within each trial block.
- Both initial bottleneck placements represented.
- Repeated trials; report n, mean, standard deviation, median, IQR, and confidence intervals. Use bootstrap intervals for skewed latency/goodput distributions where appropriate.
- Predeclare acceptable goodput and loss regressions and the primary latency success threshold before the final campaign.
- Retain raw per-flow records, time-series telemetry, controller logs, qdisc/OVS evidence, run manifest, exact commands, git revision, and dirty-tree state.
- Do not pool distinct workload/impairment conditions into a single headline number.
- Preserve the existing 400-trial, 500-trial, and runtime pilot result directories unchanged.

## Required software deliverables

1. Config-driven topology/impairment controller with reproducible event schedule.
2. TCP/UDP workload generator supporting burst schedules and mixed flow sizes.
3. Structured telemetry collector and documented CSV/JSON schema.
4. Controller instrumentation for decisions, confidence rationale, FlowMod updates, and telemetry request/reply volume.
5. Per-flow and time-series metric extraction, including latency, goodput, loss, fairness, stability, adaptation, and overhead.
6. Campaign runner with matched seeds, resume safety, immutable manifests, and cell-level checkpoints.
7. Integrity auditor that rejects missing/duplicate trials, failed clients, mismatched arrays, missing required metrics, invalid timestamps, and dirty/unexpected revisions.
8. Analysis/report generator with plots and condition-stratified statistics.

## Final campaign gate

Do not run the final campaign until:
- Unit tests cover metric calculations and parsers.
- Integration smoke tests prove telemetry, traffic, qdisc events, decision logs, rule-update counters, and cleanup.
- TCP latency measurement is validated against a known baseline and clearly distinguished from ICMP.
- Concurrent flows demonstrate Jain fairness calculation.
- UDP sequence loss and qdisc drop counters are cross-checked.
- Adaptation timestamps and settling logic pass deterministic tests.
- A complete one-cell end-to-end rehearsal passes the integrity auditor.
- Policy parameters and final campaign manifest are frozen.

## Proposed final matrix

Use a staged, balanced design rather than a combinatorial explosion. Include all five policies (static, least_loaded, threshold, stability_aware, uncertainty_aware), both initial path placements, all proposal workload families, and baseline/delayed/noisy/combined telemetry. Include degradation/recovery as a dedicated event workload. Use a development set to calibrate offered-load levels and verify the fixed success thresholds; reserve independent seeds and workload schedules for the final test set. Choose repetitions after measuring runtime in the rehearsal, targeting at least 10 matched repetitions per cell if feasible. The final exact cell count and duration must be emitted by a dry-run manifest before execution.

## Known prototype constraints to resolve or disclose

- Current forwarding makes decisions only for new flows; existing flows are not migrated.
- Existing topology has two paths and static ARP; general ARP behavior is out of scope unless needed by scenarios.
- Current live utilization is derived from OpenFlow transmit-byte counters and assumes 100 Mbps; configurable capacity must be propagated consistently to topology, controller, and experiment calculations.
- Queue statistics support varies by OVS/Mininet version. Validate actual available counters before promising queue occupancy.
- Controller CPU/RSS currently measures the Ryu process only, not OVS or host-wide overhead.
- Mininet/OVS results are emulation results, not physical-network results.
