from experiments.analyze_results import summarize
from experiments.policy_replay import POLICIES, SCENARIOS, run_replay


def test_replay_is_deterministic_and_has_complete_policy_matrix():
    first = run_replay(seed=11, trials=2, steps=3)
    second = run_replay(seed=11, trials=2, steps=3)
    assert first == second
    assert len(first) == len(SCENARIOS) * 2 * 3 * len(POLICIES)
    assert {row["policy"] for row in first} == set(POLICIES)
    assert {row["scenario"] for row in first} == set(SCENARIOS)


def test_replay_regret_is_nonnegative_and_temporal_metrics_are_valid():
    rows = run_replay(seed=3, trials=1, steps=5)
    assert all(row["regret"] >= 0 for row in rows)
    assert all(row["path_changes_so_far"] >= row["route_changed"] for row in rows)
    assert all(row["reversals_so_far"] >= row["reversal_to_previous_path"] for row in rows)
    assert all(row["path_changes_per_minute"] >= 0 for row in rows)


def test_step_interval_controls_elapsed_time_and_rate():
    rows = run_replay(seed=3, trials=1, steps=2, step_interval_s=4.0)
    sample = next(row for row in rows if row["scenario"] == SCENARIOS[0]
                  and row["policy"] == POLICIES[0] and row["step"] == 2)
    assert sample["elapsed_s"] == 8.0
    assert sample["step_interval_s"] == 4.0


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
