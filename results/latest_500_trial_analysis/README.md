# Latest 500-trial evidence

This directory documents the latest counterbalanced Mininet/OVS matrix, run against code revision `c2d8588c2346e17880e669a9990ea8873bf67c98`.

- [Verified analysis and interpretation](FINAL_ANALYSIS.md)
- [Machine-readable dataset audit](dataset_audit.json)

The original raw CSV and generated report were supplied separately from the Ubuntu VM and are preserved unchanged by the analysis workflow. The raw 500-row CSV is not duplicated in this repository commit. The downloadable analysis bundle includes derived summary data, 2,000-row successive-flow data, figures and the audit.

All results are Mininet/OVS emulation measurements. ICMP probe p99 is not TCP-flow p99. See the analysis for the metrics that remain unmeasured and the claim limitations.
