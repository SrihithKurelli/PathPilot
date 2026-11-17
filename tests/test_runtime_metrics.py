import pytest

from experiments.runtime_metrics import jain_fairness, path_transition_metrics, percentile


def test_jain_fairness_equal_throughputs():
    assert jain_fairness([10, 10, 10]) == pytest.approx(1.0)


def test_jain_fairness_unequal_throughputs():
    assert jain_fairness([10, 0]) == pytest.approx(0.5)


def test_jain_fairness_rejects_invalid_values():
    with pytest.raises(ValueError):
        jain_fairness([1, -1])


def test_percentile_interpolates():
    assert percentile([0, 10], 0.5) == pytest.approx(5)


def test_path_transition_metrics_counts_changes_and_reversals():
    result = path_transition_metrics(["A", "B", "A", "A", "B"])
    assert result == {
        "path_decision_count": 5,
        "path_changes": 3,
        "path_reversals": 2,
    }


def test_path_transition_metrics_handles_empty_and_single_path():
    assert path_transition_metrics([])["path_changes"] == 0
    assert path_transition_metrics(["A"])["path_reversals"] == 0
