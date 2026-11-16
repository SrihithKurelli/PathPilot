from experiments.path_pinning import pinned_experiment_path


def test_pin_applies_only_to_designated_first_flow_port():
    assert pinned_experiment_path("s1-s2-s4", 5001) == "s1-s2-s4"
    assert pinned_experiment_path("s1-s2-s4", 5002) is None


def test_pin_can_force_either_path():
    assert pinned_experiment_path("s1-s2-s4", 5001) == "s1-s2-s4"
    assert pinned_experiment_path("s1-s3-s4", 5001) == "s1-s3-s4"


def test_pin_is_disabled_without_configuration():
    assert pinned_experiment_path(None, 5001) is None
    assert pinned_experiment_path("", 5001) is None


def test_pin_rejects_unknown_path_and_invalid_port():
    import pytest

    with pytest.raises(ValueError):
        pinned_experiment_path("s1-s4", 5001)
    with pytest.raises(ValueError):
        pinned_experiment_path("s1-s2-s4", 70000)
