import threading

import pytest

from experiments.runtime_metrics import (
    ProcessMetricsSampler, jain_fairness, path_transition_metrics, percentile,
)


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
        "path_reversals": 1,
    }


def test_path_transition_metrics_handles_empty_and_single_path():
    assert path_transition_metrics([])["path_changes"] == 0
    assert path_transition_metrics(["A"])["path_reversals"] == 0


def test_process_metrics_stop_is_idempotent(monkeypatch):
    class FinishedThread:
        def join(self, timeout=None):
            pass

    sampler = ProcessMetricsSampler(123)
    sampler._thread = FinishedThread()
    sampler._start_wall = 10.0
    sampler._start_cpu = 100
    sampler._peak_rss_kb = 2048
    monkeypatch.setattr(sampler, "_read", lambda: (200, 3072))
    import os
    monkeypatch.setattr(os, "sysconf", lambda key: 100)
    clock = iter([12.0, 20.0])
    monkeypatch.setattr("experiments.runtime_metrics.time.monotonic", lambda: next(clock))

    first = sampler.stop()
    second = sampler.stop()

    assert first == second
    assert first["controller_cpu_seconds"] == 1.0
    assert first["controller_cpu_percent_mean"] == 50.0
    assert first["controller_rss_peak_mb"] == 3.0
