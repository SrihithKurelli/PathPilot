from experiments.final_campaign import build_manifest


def test_campaign_is_counterbalanced_and_seed_matched():
    manifest = build_manifest(
        repetitions=2,
        scenarios=["steady_low"],
        conditions=["baseline"],
    )
    assert manifest["trial_count"] == 2 * 2 * 5
    groups = {}
    for row in manifest["trials"]:
        key = (row["scenario"], row["telemetry_condition"],
               row["initial_bottleneck_path"], row["repetition"])
        groups.setdefault(key, set()).add(row["workload_seed"])
    assert all(len(seeds) == 1 for seeds in groups.values())


def test_development_and_final_test_are_separated():
    dev = build_manifest(repetitions=1, scenarios=["steady_low"],
                         conditions=["baseline"], development=True)
    test = build_manifest(repetitions=1, scenarios=["steady_low"],
                          conditions=["baseline"])
    assert {row["split"] for row in dev["trials"]} == {"development"}
    assert {row["split"] for row in test["trials"]} == {"final_test"}


def test_unknown_campaign_factor_rejected():
    import pytest
    with pytest.raises(ValueError):
        build_manifest(scenarios=["not_a_scenario"])
