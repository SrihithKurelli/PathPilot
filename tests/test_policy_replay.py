from experiments.analyze_results import summarize
from experiments.policy_replay import run_replay


def test_replay_is_deterministic_and_has_complete_policy_matrix():
    first = run_replay(seed=11, trials=2, steps=3)
    second = run_replay(seed=11, trials=2, steps=3)
    assert first == second
    assert len(first) == 6 * 2 * 3 * 5
    assert {row["policy"] for row in first} == {
        "static", "least_loaded", "threshold", "stability_aware", "uncertainty_aware"
    }


def test_replay_regret_is_nonnegative():
    rows = run_replay(seed=3, trials=1, steps=5)
    assert all(row["regret"] >= 0 for row in rows)


def test_summary_groups_by_scenario_and_policy():
    rows = [
        {"scenario": "x", "policy": "p", "regret": "0.1",
         "selected_true_utilization": "0.4", "oracle_choice": "1",
         "selected_confidence": "0.9"},
        {"scenario": "x", "policy": "p", "regret": "0.3",
         "selected_true_utilization": "0.6", "oracle_choice": "0",
         "selected_confidence": "0.7"},
    ]
    result = summarize(rows)
    assert len(result) == 1
    assert result[0]["decisions"] == 2
    assert result[0]["mean_regret"] == 0.2
    assert result[0]["oracle_choice_rate"] == 0.5
