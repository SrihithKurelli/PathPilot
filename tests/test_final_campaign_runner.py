import json

import pytest

from experiments.final_campaign import build_manifest
from experiments.run_final_campaign import execute, trial_directory


def test_final_campaign_manifest_has_all_factors_and_expected_count():
    manifest = build_manifest(repetitions=2)
    assert manifest["trial_count"] == 20 * 2 * 5 * 2
    assert len({row["policy"] for row in manifest["trials"]}) == 5
    assert {row["initial_bottleneck_path"] for row in manifest["trials"]} == {
        "s1-s2-s4", "s1-s3-s4"
    }


def test_trial_directory_is_factorized_and_stable(tmp_path):
    row = {
        "scenario": "steady_low", "telemetry_condition": "baseline",
        "initial_bottleneck_path": "s1-s2-s4", "policy": "least_loaded",
        "repetition": 3,
    }
    assert trial_directory(tmp_path, row) == (
        tmp_path / "steady_low" / "baseline" / "s1-s2-s4"
        / "least_loaded" / "rep_003"
    )


def test_campaign_runner_dry_run_does_not_execute_mininet(tmp_path):
    manifest = build_manifest(
        repetitions=1, scenarios=["steady_low"], conditions=["baseline"],
        initial_paths=["s1-s2-s4"], policies=["static"],
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    result = execute(manifest_path, tmp_path / "results", dry_run=True)
    assert result["planned"] == 1
    assert result["completed_or_skipped"] == 0
    assert not (tmp_path / "results").exists()


def test_campaign_runner_rejects_development_manifest(tmp_path):
    manifest = build_manifest(
        repetitions=1, scenarios=["steady_low"], conditions=["baseline"],
        initial_paths=["s1-s2-s4"], policies=["static"], development=True,
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        execute(manifest_path, tmp_path / "results", dry_run=True)


def test_development_manifest_requires_explicit_opt_in(tmp_path):
    manifest = build_manifest(
        repetitions=1, scenarios=["steady_low"], conditions=["baseline"],
        initial_paths=["s1-s2-s4"], policies=["static"], development=True,
    )
    manifest_path = tmp_path / "development.json"
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        execute(manifest_path, tmp_path / "out", dry_run=True)
    result = execute(manifest_path, tmp_path / "out", dry_run=True,
                     allow_development=True)
    assert result["planned"] == 1


def test_fractional_design_keeps_full_impairment_factorial_for_bursts():
    manifest = build_manifest(repetitions=1)
    burst_conditions = {
        row["telemetry_condition"] for row in manifest["trials"]
        if row["scenario"] in {"sudden_burst", "alternating_bursts"}
    }
    steady_conditions = {
        row["telemetry_condition"] for row in manifest["trials"]
        if row["scenario"] in {"steady_low", "steady_high"}
    }
    assert burst_conditions == {"baseline", "delayed", "noisy", "combined"}
    assert steady_conditions == {"baseline", "combined"}
