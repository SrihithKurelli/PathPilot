import json

import pytest

from controller.policies import Telemetry
from controller.telemetry_loader import (
    EXPECTED_PATHS,
    conservative_telemetry,
    load_static_telemetry,
)


VALID_DATA = {
    "s1-s2-s4": {"utilization": 0.2, "age_s": 0.1, "variability": 0.02},
    "s1-s3-s4": {"utilization": 0.4, "age_s": 0.2, "variability": 0.03},
}


def write_json(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_loads_complete_valid_static_telemetry(tmp_path):
    path = write_json(tmp_path / "telemetry.json", VALID_DATA)
    result = load_static_telemetry(path)
    assert tuple(result) == EXPECTED_PATHS
    assert result["s1-s2-s4"] == Telemetry(0.2, 0.1, 0.02)


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"s1-s2-s4": VALID_DATA["s1-s2-s4"]},
        {**VALID_DATA, "unexpected-path": VALID_DATA["s1-s2-s4"]},
        {"s1-s2-s4": [], "s1-s3-s4": VALID_DATA["s1-s3-s4"]},
        {
            **VALID_DATA,
            "s1-s2-s4": {**VALID_DATA["s1-s2-s4"], "unexpected": 1},
        },
        {
            **VALID_DATA,
            "s1-s2-s4": {**VALID_DATA["s1-s2-s4"], "utilization": 1.2},
        },
        {
            **VALID_DATA,
            "s1-s2-s4": {**VALID_DATA["s1-s2-s4"], "age_s": -1},
        },
        {
            **VALID_DATA,
            "s1-s2-s4": {**VALID_DATA["s1-s2-s4"], "variability": "noisy"},
        },
        {
            **VALID_DATA,
            "s1-s2-s4": {**VALID_DATA["s1-s2-s4"], "utilization": True},
        },
    ],
)
def test_rejects_incomplete_or_invalid_static_telemetry(tmp_path, data):
    path = write_json(tmp_path / "telemetry.json", data)
    with pytest.raises(ValueError):
        load_static_telemetry(path)


def test_rejects_invalid_json(tmp_path):
    path = tmp_path / "telemetry.json"
    path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ValueError):
        load_static_telemetry(path)


def test_rejects_missing_file(tmp_path):
    with pytest.raises(ValueError):
        load_static_telemetry(tmp_path / "missing.json")


def test_conservative_fallback_is_complete_and_untrusted():
    result = conservative_telemetry()
    assert tuple(result) == EXPECTED_PATHS
    for sample in result.values():
        sample.validate()
        assert sample.age_s == 999.0
        assert sample.variability == 1.0
