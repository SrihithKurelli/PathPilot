import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "experiments" / "run_telemetry_matrix.py"
SPEC = importlib.util.spec_from_file_location("run_telemetry_matrix", MODULE_PATH)
matrix = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(matrix)


def test_matrix_contains_expected_impairment_conditions():
    assert matrix.CONDITIONS == {
        "baseline": (0.0, 0.0),
        "delayed": (2.0, 0.0),
        "noisy": (0.0, 0.05),
        "combined": (2.0, 0.05),
        "severe_combined": (4.0, 0.10),
    }


def test_default_matrix_has_200_trials_at_ten_repeats():
    assert len(matrix.CONDITIONS) * len(matrix.POLICIES) * 10 == 200


def test_summary_groups_by_condition_and_policy():
    rows = [
        {
            "condition": "baseline",
            "policy": "static",
            "second_flow_mbps": "10",
            "avoided_bottleneck": "0",
            "connectivity_loss_pct": "0",
        },
        {
            "condition": "baseline",
            "policy": "static",
            "second_flow_mbps": "12",
            "avoided_bottleneck": "1",
            "connectivity_loss_pct": "0",
        },
        {
            "condition": "delayed",
            "policy": "static",
            "second_flow_mbps": "8",
            "avoided_bottleneck": "0",
            "connectivity_loss_pct": "0",
        },
    ]
    summary = matrix.summarize(rows)
    assert len(summary) == 2
    baseline = next(row for row in summary if row["condition"] == "baseline")
    delayed = next(row for row in summary if row["condition"] == "delayed")
    assert baseline["trials"] == 2
    assert baseline["mean_second_flow_mbps"] == 11
    assert baseline["bottleneck_avoidance_rate"] == 0.5
    assert delayed["trials"] == 1
    assert delayed["mean_second_flow_mbps"] == 8


def test_report_includes_scope_and_limitations(tmp_path):
    row = {
        "condition": "baseline",
        "telemetry_delay_seconds": 0.0,
        "telemetry_noise_std": 0.0,
        "policy": "static",
        "trials": 1,
        "mean_second_flow_mbps": 10.0,
        "std_second_flow_mbps": 0.0,
        "bottleneck_avoidance_rate": 0.0,
        "mean_connectivity_loss_pct": 0.0,
    }
    output = tmp_path / "REPORT.md"
    matrix.write_report(output, [row], 1)
    report = output.read_text()
    assert "Mininet emulation results" in report
    assert "does not measure p99 latency" in report

def test_aggregate_csv_preserves_telemetry_evidence():
    assert "first_telemetry_log" in matrix.RAW_FIELDS
    assert "second_telemetry_log" in matrix.RAW_FIELDS

