import csv
import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "experiments" / "run_balanced_path_matrix.py"
SPEC = importlib.util.spec_from_file_location("run_balanced_path_matrix", MODULE_PATH)
balanced = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(balanced)


def test_matrix_covers_both_initial_paths():
    assert balanced.PATHS == {
        "path1": "s1-s2-s4",
        "path2": "s1-s3-s4",
    }


def test_summary_reports_median_and_inclusive_iqr():
    rows = [
        {
            "condition": "baseline",
            "initial_path": "s1-s2-s4",
            "policy": "static",
            "second_flow_mbps": str(value),
            "avoided_bottleneck": "0",
            "connectivity_loss_pct": "0",
        }
        for value in (1, 2, 3, 4, 5)
    ]
    result = balanced.summarize(rows)[0]
    assert result["trials"] == 5
    assert result["median_second_flow_mbps"] == 3
    assert result["q1_second_flow_mbps"] == 2
    assert result["q3_second_flow_mbps"] == 4
    assert result["iqr_second_flow_mbps"] == 2


def test_cell_loader_keeps_initial_path_separate(tmp_path):
    for path_key, path_name in balanced.PATHS.items():
        output = balanced.cell_file(tmp_path, "baseline", path_key)
        with output.open("w", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["policy", "first_flow_path", "second_flow_mbps",
                            "avoided_bottleneck", "connectivity_loss_pct"],
            )
            writer.writeheader()
            for policy in balanced.POLICIES:
                writer.writerow({
                    "policy": policy,
                    "first_flow_path": path_name,
                    "second_flow_mbps": "80",
                    "avoided_bottleneck": "1",
                    "connectivity_loss_pct": "0",
                })

    rows = balanced.load_completed_cells(tmp_path)
    assert len(rows) == 2 * len(balanced.POLICIES)
    assert {row["initial_path"] for row in rows} == set(balanced.PATHS.values())
    assert len(balanced.summarize(rows)) == 2 * len(balanced.POLICIES)


def test_cell_loader_rejects_wrong_pinned_path(tmp_path):
    output = balanced.cell_file(tmp_path, "baseline", "path1")
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["policy", "first_flow_path", "second_flow_mbps",
                        "avoided_bottleneck", "connectivity_loss_pct"],
        )
        writer.writeheader()
        for policy in balanced.POLICIES:
            writer.writerow({
                "policy": policy,
                "first_flow_path": "s1-s3-s4",
                "second_flow_mbps": "80",
                "avoided_bottleneck": "1",
                "connectivity_loss_pct": "0",
            })
    import pytest
    with pytest.raises(RuntimeError, match="expected pinned first path"):
        balanced.load_completed_cells(tmp_path)



def test_raw_fields_retain_iperf_diagnostics():
    assert "first_flow_client_returncode" in balanced.RAW_FIELDS
    assert "second_flow_client_returncode" in balanced.RAW_FIELDS
    assert "first_flow_iperf_output" in balanced.RAW_FIELDS
    assert "second_flow_iperf_output" in balanced.RAW_FIELDS
