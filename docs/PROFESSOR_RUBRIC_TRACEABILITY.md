# Professor Rubric Traceability — PathPilot (post-PR #12)

This document maps the Project Orientation PDF and the revised PathPilot proposal to the implementation at the merged baseline and the latest locally completed experiment. It deliberately separates implemented software, measured outcomes, and work still required. A feature is not marked evaluated merely because code exists.

## 1. Professor's Project Orientation rubric

| Evaluation dimension | Evidence | Current assessment | Remaining work |
|---|---|---|---|
| Networked software / SDN mechanism | Ryu OpenFlow 1.3 controller, Open vSwitch and Mininet two-path topology | Implemented and exercised | Capture final live-demo evidence from the project VM |
| Motivation and prior work | Revised proposal frames uncertain/stale telemetry as the problem and explicitly cautions against claiming generic hysteresis or stability as novel | Partially documented | Final related-work section with verified full bibliographic details and a careful comparison to HAASP and related systems |
| Problem formulation | Proposal research question compares uncertainty-aware new-flow placement with static, least-loaded, threshold and stability-aware baselines under impaired telemetry | Defined; novelty remains conditional | State the contribution as a tested design/evaluation unless a full-text literature audit supports a stronger novelty claim |
| System design | Controller, telemetry, policy modules, Mininet topology and repeatable experiment runner | Implemented | Include final architecture diagram, flow-selection sequence diagram and policy pseudocode in final report |
| Module implementation | Controller, topology, live telemetry, static telemetry validation, policy logic, experiment runners, analyzer and tests | Core modules implemented | Add any optional metric instrumentation only where it can be validated end-to-end |
| End-to-end integration | CI Mininet smoke workflow plus 500-trial Mininet/OVS matrix executed on the Ubuntu VM | Implemented; local full-matrix evidence exists | Capture a short guided demonstration on the actual submission VM and preserve logs/screenshots |
| Performance evaluation | 500-trial counterbalanced matrix across five policies, five telemetry conditions and two bottleneck placements; 10 repetitions per cell | Substantial, but not complete against proposal metrics | Add latency/fairness/overhead metrics and missing traffic/failure scenarios, or explicitly narrow the final research question and justify the scope |
| Near-real-world deployment | Ryu + OVS + Mininet emulation | Meets the orientation's emulation/deployment direction | Demonstrate live traffic and policy decisions; label all results as emulation, not physical deployment |
| Presentation quality | Existing runbook and report material | Not yet submission-ready | Final report, architecture/flow diagrams, plots, demo evidence, concise presentation and references |

The orientation PDF (pages 2–4 and 7) accepts SDN/networked software and emulation, but stresses motivation/references, completed end-to-end integration, completed performance evaluation, and a live or emulated deployment. Its page-3 rubric gives the strongest category only when integration and performance evaluation are completed as well as the system and modules.

## 2. Revised proposal traceability

| Proposal requirement | Current evidence | Status |
|---|---|---|
| Multi-path Mininet/OVS topology | `topology/mininet_topology.py` | Implemented: two alternative paths |
| Configurable capacity, delay, loss and bottleneck events | Fixed topology link configuration and TBF bottleneck experiment | Partial: bottleneck and telemetry delay/noise are exercised; generalized loss/failure and arbitrary per-link configuration are not complete |
| Utilization telemetry | OpenFlow port tx-byte deltas in `controller/live_telemetry.py` | Implemented |
| Queue/drop counters | No queue occupancy/drop telemetry collector | Missing |
| End-to-end latency | Concurrent ICMP RTT p50/p95/p99 probe | Partial: ICMP is a separate probe flow; no per-TCP-flow latency distribution or TCP p99 |
| Sampling delay and measurement noise | Historical counter samples and configurable noise in Mininet runner | Implemented and exercised |
| Static, least-loaded, threshold policies | `controller/policies.py` | Implemented and compared |
| Stability-aware baseline | Fixed 0.10 absolute-utilization improvement threshold | Implemented and compared; baseline only, not a novelty claim |
| Uncertainty-aware new-flow placement | Confidence based on sample age and variability; confidence-qualified selection and explicit fallback | Implemented and exercised; heuristic, not a statistically calibrated uncertainty estimator |
| Existing flows stay on their selected path | Per-flow forwarding rules; no migration logic | Implemented for the prototype |
| Repeatable runner and provenance | Fixed seeds, trial-level CSV, controller logs, Git revision and dirty-tree metadata | Implemented |
| Counterbalanced path placement | Five policies × five conditions × two bottleneck placements × ten repetitions | 500-trial matrix completed locally (500 trials); raw outputs currently remain on the Ubuntu VM |
| Successive new-flow fallback behavior | Four policy-selected TCP flows per trial under one controller; fallback audit | Audited: 400 uncertainty-aware successive decisions, 298 fallback invocations; all-fallback trials alternate paths. Rotation is load balancing, not congestion identification |
| Steady low/high load | Synthetic policy replay; Mininet baseline condition | Partial: baseline Mininet condition is not a complete offered-load sweep |
| Sudden/alternating bursts | Synthetic temporal replay | Partial: not yet a corresponding controlled Mininet traffic workload |
| Mixed short/long flows | Synthetic aggregate-load proxy | Partial: not a packet-level Mininet mixed-flow experiment |
| Path degradation/link loss and recovery | TBF bottleneck only | Partial: link failure/recovery experiment absent |
| Goodput | TCP iperf goodput for first and successive policy-selected flows | Measured |
| Packet loss | Connectivity/ICMP probe loss | Partial: no TCP data-plane loss metric |
| Jain fairness | Not collected | Missing |
| Routing stability | Path decisions in experiment logs; synthetic replay reports temporal changes/reversals | Partial: no live Mininet path-change rate/reversal analysis for a concurrent-flow workload |
| Adaptation/settling time | Not collected as a defined metric | Missing |
| Controller CPU, rule updates, telemetry volume | Not collected systematically | Missing |
| Repeated trials and variability | Ten repetitions per policy/condition/placement; mean, median, standard deviation, quartiles | Implemented for the current goodput/path-choice matrix; no inferential significance claim |

## 3. Latest experiment facts to preserve

The latest Ubuntu VM matrix is separate from the historical 400-trial archive committed in `results/balanced_full/`.

- Latest matrix: 500 trials = 5 policies × 5 telemetry conditions × 2 bottleneck placements × 10 repetitions.
- Each trial includes four successive policy-selected TCP flows after a pinned priming flow: 2,000 successive-flow measurements in total.
- Dataset audit reported 500 unique trial keys, no duplicate trials, no malformed/mismatched successive-flow arrays, four successive flows in every row, and zero nonzero successive-flow client return codes.
- All 2,000 successive-flow client runs returned exit code 0.
- Local project verification on the merged branch: `compileall` succeeded and `pytest` reported 74 passed.
- Fallback audit: 100 uncertainty-aware trials and 400 successive decisions; 298 decisions invoked low-confidence fallback (159 Path 1, 139 Path 2); 60 trials used fallback for all four decisions, 39 were mixed, and one used no fallback. Every all-fallback trial alternated Path 1/Path 2 for its four decisions.
- In the combined, delayed and severe-combined conditions, the fallback audit found all four decisions falling back in every trial. This demonstrates the fallback's operation under low confidence, not that it identifies the uncongested path.
- ICMP p99 is a separate probe-flow RTT under concurrent TCP load. It is not TCP-flow p99 latency.
- The current matrix does not measure Jain fairness, TCP packet loss, controller CPU, flow-rule update overhead, or settling time.

The full latest raw dataset and generated report are in the VM at `results/round_robin_balanced_matrix/`. They are not part of this repository snapshot. Do not cite numerical table entries from that run until the generated report and CSVs have been copied into the submission evidence bundle and checked.

## 4. Highest-priority remaining work

1. **Evidence and reproducibility:** add the latest 500-trial report, summary, raw data or a compressed reproducibility bundle to the repository/submission archive. Preserve the older 400-trial archive separately and label it historical.
2. **Final live demo:** run the guided Ryu/Mininet demonstration on the project Ubuntu VM; capture topology, switch connection/telemetry logs, successful connectivity, one policy decision, controlled bottleneck and generated result CSV.
3. **Latency and loss:** if time permits, instrument per-TCP-flow latency and TCP data-plane loss. Otherwise explicitly narrow the research question and report these as limitations; do not substitute ICMP p99 for TCP p99.
4. **Fairness:** run simultaneous competing flows and calculate Jain's fairness index from per-flow goodput.
5. **Stability and adaptation:** run a time-varying multi-flow Mininet workload and record controller decisions with timestamps; calculate path changes/minute, reversals within a predeclared window, and settling time.
6. **Overhead:** collect controller CPU, flow-rule update counts and telemetry message/byte volume with a documented measurement method.
7. **Scenario coverage:** add controlled low/high offered load, burst/alternating burst, short/long flow mix, and link degradation/failure/recovery, or justify why these are out of scope.
8. **Final report and presentation:** add architecture and sequence diagrams, pseudocode, exact experiment configuration/seeds, plots, trial counts, variability, anomalies, limitations and verified references.
9. **Literature/novelty audit:** verify the full HAASP source and relevant related work. Do not claim generic hysteresis, routing stability, historical costs or round-robin fallback as novel.

## 5. Claim discipline

- Results are Mininet/Open vSwitch emulation results, not physical-network or production measurements.
- The measured network outcome is TCP goodput and path selection/avoidance. ICMP probe RTT percentiles are separate-flow measurements.
- The uncertainty-aware policy is a heuristic using freshness and variability. Round-robin fallback distributes successive uncertain decisions; it does not infer congestion.
- Ten repetitions per matrix cell support descriptive comparisons, not a claim of statistical significance.
- Do not claim the full proposal metrics are satisfied until the missing measurements are implemented, run and audited.
