import csv

from experiments.plot_final_campaign import plot_summary, write_bar_chart


def test_svg_plot_generation_is_dependency_free(tmp_path):
    target = tmp_path / "plot.svg"
    rows = [
        {"policy": "least_loaded", "tcp_app_rtt_p99_ms_mean": "20"},
        {"policy": "uncertainty_aware", "tcp_app_rtt_p99_ms_mean": "15"},
    ]
    assert write_bar_chart(rows, "tcp_app_rtt_p99_ms", "RTT comparison", target)
    text = target.read_text()
    assert "<svg" in text
    assert "uncertainty_aware" in text


def test_plot_summary_creates_condition_stratified_files(tmp_path):
    source = tmp_path / "summary.csv"
    rows = [
        {"scenario": "steady_low", "condition": "baseline",
         "initial_path": "s1-s2-s4", "policy": "least_loaded",
         "tcp_app_rtt_p99_ms_mean": "10", "aggregate_goodput_mbps_mean": "50",
         "path_changes_per_minute_mean": "2", "jain_fairness_mean": "1"},
    ]
    with source.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    outputs = plot_summary(source, tmp_path / "plots")
    assert len(outputs) == 4
    assert all(path.endswith(".svg") for path in outputs)
