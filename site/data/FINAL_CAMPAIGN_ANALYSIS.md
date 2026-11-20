# PathPilot Final Campaign Analysis

- Trials analyzed: 599
- Source revision: 5bd52e936d72f714480a4fef5960d9cf782b04bf
- Policies: static, least_loaded, threshold, stability_aware, uncertainty_aware
- Scenarios: steady_low, steady_high, sudden_burst, alternating_bursts, mixed_short_long, degrade_recover, link_loss_recovery, loss_recovery
- Telemetry conditions: baseline, delayed, noisy, combined

Generated 156 condition-stratified SVG plots in plots/.
Preregistered threshold evaluations: 12 matched comparisons in combined-telemetry burst workloads; see PREREGISTERED_THRESHOLD_EVALUATION.csv.
The CSV files report condition- and initial-path-stratified metrics with trial-level bootstrap 95% intervals. Paired comparisons use matched scenario/condition/path/repetition blocks.

TCP application RTT is measured by the dedicated TCP echo probe under concurrent workload. UDP packet loss is reported only for UDP flows. Jain fairness is calculated only for time windows with at least two competing flows. Controller CPU/RSS are Ryu-process-only. Telemetry byte totals include estimated reply sizes when serialized buffers are unavailable.

Do not pool workload families or telemetry conditions into one headline value. Evaluate the preregistered thresholds in the campaign manifest and report failures or mixed outcomes without post-hoc threshold changes.
