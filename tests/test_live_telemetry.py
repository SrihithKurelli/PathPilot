import pytest

from controller.live_telemetry import PortRateTracker


def sample_path(tracker, now, s2_bytes=0, s3_bytes=0):
    # First-hop egress counters are updated on s1; second-hop counters on
    # s2/s3. Each sample represents the same interval.
    tracker.update_port(1, 2, s2_bytes, now)
    tracker.update_port(2, 2, s2_bytes, now)
    tracker.update_port(1, 3, s3_bytes, now)
    tracker.update_port(3, 2, s3_bytes, now)


def test_first_counter_sample_only_establishes_baseline():
    tracker = PortRateTracker()
    sample_path(tracker, 0.0, 1000, 2000)
    assert tracker.path_telemetry(0.0) is None


def test_path_utilization_uses_maximum_link_utilization():
    tracker = PortRateTracker()
    # 1 second interval: 10 MB = 80 Mbps, 5 MB = 40 Mbps.
    sample_path(tracker, 0.0, 0, 0)
    sample_path(tracker, 1.0, 10_000_000, 5_000_000)
    telemetry = tracker.path_telemetry(1.0)
    assert telemetry["s1-s2-s4"].utilization == pytest.approx(0.8)
    assert telemetry["s1-s3-s4"].utilization == pytest.approx(0.4)


def test_stale_port_samples_are_not_used():
    tracker = PortRateTracker(max_age_s=3.0)
    sample_path(tracker, 0.0)
    sample_path(tracker, 1.0, 1_000_000, 1_000_000)
    assert tracker.path_telemetry(5.0) is None


def test_counter_reset_discards_rate_until_next_interval():
    tracker = PortRateTracker()
    tracker.update_port(1, 2, 10_000, 0.0)
    tracker.update_port(1, 2, 1_000, 1.0)
    assert tracker.path_telemetry(1.0) is None
    tracker.update_port(1, 2, 2_000, 2.0)
    assert (1, 2) in tracker._utilization


def test_untracked_ports_are_ignored():
    tracker = PortRateTracker()
    tracker.update_port(4, 3, 1_000, 0.0)
    assert tracker._previous == {}


def test_invalid_configuration_is_rejected():
    with pytest.raises(ValueError):
        PortRateTracker(capacity_bps=0)
