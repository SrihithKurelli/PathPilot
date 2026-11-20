# PathPilot results site and deployment

The static site in `site/` presents the 599 audit-passing trials from the 20 November 2026 curation of the 19 November campaign. It is a presentation and evidence surface for the SDN prototype; it does not replace the Ryu + Mininet + Open vSwitch live emulated demonstration.

## Data provenance

- The source manifest contains 600 planned trials at revision `5bd52e936d72f714480a4fef5960d9cf782b04bf`, with a clean source tree.
- The original strict audit found one failure: impairment execution error in `link_loss_recovery / combined / s1-s3-s4 / uncertainty_aware / rep 001` while restoring `s2-eth2`. Its outage recovery timestamp and duration are absent.
- That cell is excluded from the filtered manifest and all displayed aggregates. The other 599 trial records have the expected raw artifacts and passed strict per-trial checks.
- CSV summaries are produced by `experiments/analyze_final_campaign.py` on the filtered manifest. The source result tree is preserved; the generated CSV/JSON files in `site/data/` are curated presentation artifacts, not replacements for raw evidence.

## Publish with GitHub Pages

The workflow `.github/workflows/pages.yml` deploys the static `site/` directory from `codex/pathpilot-implementation-followup` after the repository has Pages configured to use GitHub Actions. The repository must permit Pages builds for this private project, and the workflow needs the standard `pages: write` and `id-token: write` permissions declared in the workflow. The first successful Actions run publishes the URL in its `github-pages` environment.

If Pages is not enabled for this repository, an owner must enable it under **Settings → Pages → Build and deployment → GitHub Actions**. A static site deployment presents experiment results; the evaluation-day network demo still needs the Linux/WSL environment and should follow `DEMO_RUNBOOK.md`.

## Evaluation framing

Report per-scenario and per-telemetry-condition results. Keep TCP echo RTT p99 distinct from ICMP latency; keep UDP loss limited to UDP flows; explain fairness windows and controller-only CPU/RSS. State emulation limitations, report guardrails that were not met or incomplete, and avoid describing the uncertainty-aware prototype as a proven novel algorithm.
