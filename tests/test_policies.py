import pytest

from controller.policies import Telemetry, confidence, choose_path


@pytest.fixture
def samples():
    return {"path-a": Telemetry(.2, .1, .01), "path-b": Telemetry(.6, .1, .01)}


def test_confidence_bounds_and_age():
    fresh = confidence(Telemetry(.2, 0, 0))
    stale = confidence(Telemetry(.2, 10, 0))
    assert 0 <= stale < fresh <= 1


def test_variability_reduces_confidence():
    assert confidence(Telemetry(.2, .1, .5)) < confidence(Telemetry(.2, .1, 0))


def test_least_loaded(samples):
    assert choose_path(samples, "least_loaded") == "path-a"


def test_static_deterministic(samples):
    assert choose_path(samples, "static") == "path-a"


def test_threshold(samples):
    assert choose_path(samples, "threshold", threshold=.3) == "path-a"


def test_uncertainty_aware_ignores_stale_low_load():
    data = {"stale": Telemetry(.05, 20, .8), "fresh": Telemetry(.4, 0, 0)}
    assert choose_path(data, "uncertainty_aware", min_confidence=.5) == "fresh"


def test_uncertainty_aware_uses_least_loaded_when_all_samples_are_uncertain():
    # Mirrors the 2.6-second delayed telemetry experiment:
    # exp(-0.5 * 2.6) ~= 0.273, below the default 0.5 threshold.
    data = {
        "path-a": Telemetry(.103, 2.6, 0),
        "path-b": Telemetry(0.0, 2.6, 0),
    }
    assert choose_path(data, "uncertainty_aware") == "path-b"


def test_uncertainty_aware_uses_confident_candidates_when_available():
    data = {
        "uncertain_low_load": Telemetry(.05, 2.6, 0),
        "confident": Telemetry(.4, 0.1, 0),
    }
    assert choose_path(data, "uncertainty_aware") == "confident"


def test_invalid_measurement():
    with pytest.raises(ValueError):
        confidence(Telemetry(1.2, 0, 0))


def test_unknown_policy(samples):
    with pytest.raises(ValueError):
        choose_path(samples, "magic")
