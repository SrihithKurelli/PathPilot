# PathPilot final presentation guide

Use this as a 7–8 minute presentation with the `site/` results dashboard open for the results and demo sections. Keep the live Ryu/Mininet demonstration separate from the hosted dashboard: the dashboard presents measured campaign data; the live emulated network demonstrates the running controller.

## Suggested slide sequence

### 1. Problem and question — 45 seconds

Explain that static path assignment can leave parallel network capacity underused when flows collide on a bottleneck. State the project question narrowly: how do candidate path-selection policies compare when load changes and controller telemetry is delayed or noisy?

### 2. System design — 60 seconds

Show the two-path Mininet topology and the control/data path: the Ryu controller receives OpenFlow statistics from Open vSwitch, computes a route for each new flow, and installs forwarding rules. Existing flows remain pinned. Mention that the project compares static, least-loaded, threshold, stability-aware, and uncertainty-aware policies.

### 3. Scenario and measurement design — 60 seconds

The prior campaign manifest planned 600 matched trials across eight workload families, five policies, two initial bottleneck paths, and baseline/delayed/noisy/combined telemetry conditions. The presentation dataset includes the 599 records that passed strict per-trial artifact checks. One link-loss-recovery cell is excluded because its link-restoration impairment command failed and its recovery time was not measured.

Define the primary outcome precisely: TCP application RTT p99 from a dedicated echo probe during concurrent traffic. Goodput is receiver-side delivered data over receiver duration; UDP loss is only for UDP flows; Jain fairness uses windows with competing flows. Controller CPU and RSS are Ryu-process measurements. Do not call the TCP metric ICMP latency.

### 4. Results — 90 seconds

Open the dashboard with `sudden_burst`, `combined`, and `s1-s2-s4` selected. Explain that the 12 preregistered combined-telemetry burst comparisons test p99 improvement alongside goodput, UDP-loss, fairness, and path-stability guardrails. None met all guardrails together; p99 was not met in 11/12 comparisons and the path-change objective in 9/12.

For one transparent example, in this selected five-trial slice, least-loaded mean TCP application RTT p99 was 96.19 ms and uncertainty-aware was 97.29 ms. The matched relative p99 improvement estimate for uncertainty-aware versus least-loaded was −4.46% (95% interval −12.69% to −0.26%), so it was worse for this slice. Use the dashboard to show that outcomes vary by workload and comparator; do not announce a single universal winner.

### 5. Live emulated demo — 2 minutes

Follow `docs/DEMO_RUNBOOK.md`: start Ryu, start the Mininet/OVS topology, confirm connectivity, generate a controlled flow, then induce a bottleneck or telemetry impairment. Show the observed path decision and the measured traffic result. Keep one known-good fallback scenario ready in case the live setup takes time. Do not run two Mininet topologies simultaneously.

### 6. Interpretation and limitations — 60 seconds

Say what the results support: the prototype records decisions, telemetry, traffic measures, and controller overhead under a repeatable emulated workload. Say what they do not establish: production-network performance, seamless migration of existing flows, or that the uncertainty-aware extension beats all baselines. Identify the weakest acceptance outcomes and the next step: revise policy thresholds using development workloads, freeze a new configuration, then evaluate it on a new untouched final set.

### 7. Questions — 30 seconds

Be ready to explain why one trial was excluded, how paired seeds work, why p99 is measured at the application probe, and why Mininet counts as emulation rather than physical deployment.

## Rubric coverage checklist

- **Motivation and prior work:** connect multipath path selection to OpenFlow/SDN and cite related flow scheduling work.
- **System design:** show the topology, controller, OpenFlow telemetry, policies, and traffic path.
- **Implementation:** demonstrate actual Ryu decisions and installed rules, not only a dashboard animation.
- **Integration:** show controller, OVS, Mininet hosts, impairment controls, and traffic generator working together.
- **Performance evaluation:** present matched trials, condition-stratified results, uncertainty intervals, preregistered thresholds, and the excluded cell.
- **Presentation quality:** define metrics before interpreting them; label emulation; keep a saved dashboard view and a known-good demo scenario ready.

## References for the final slide

1. N. McKeown et al., “OpenFlow: Enabling Innovation in Campus Networks,” *ACM SIGCOMM Computer Communication Review*, 38(2), 69–74, 2008. [doi:10.1145/1355734.1355746](https://doi.org/10.1145/1355734.1355746).
2. M. Al-Fares et al., “Hedera: Dynamic Flow Scheduling for Data Center Networks,” *7th USENIX Symposium on Networked Systems Design and Implementation*, 2010. [USENIX paper page](https://www.usenix.org/conference/nsdi10-0/hedera-dynamic-flow-scheduling-data-center-networks).
3. B. Lantz, B. Heller, and N. McKeown, “A Network in a Laptop: Rapid Prototyping for Software-Defined Networks,” *10th ACM Workshop on Hot Topics in Networks*, 2010. [doi:10.1145/1868447.1868466](https://doi.org/10.1145/1868447.1868466).
4. Ryu SDN Framework, [official documentation](https://ryu.readthedocs.io/en/stable/ofproto_v1_3_ref.html).
