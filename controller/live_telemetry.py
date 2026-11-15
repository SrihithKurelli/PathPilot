"""Derive path utilization from OpenFlow port-transmit counters.

The tracker retains a short timestamped history so experiments can request a
measurement as it would have appeared after a controlled telemetry delay.
"""
from collections import deque
from statistics import pstdev

from controller.policies import Telemetry


PATH_EGRESS_PORTS = {
    "s1-s2-s4": ((1, 2), (2, 2)),
    "s1-s3-s4": ((1, 3), (3, 2)),
}
LINK_CAPACITY_BPS = 100_000_000
SAMPLES_PER_PORT = 5
HISTORY_SAMPLES_PER_PORT = 64
DEFAULT_MAX_AGE_S = 6.0


class PortRateTracker:
    """Convert cumulative OpenFlow tx_bytes counters into path telemetry."""

    def __init__(self, capacity_bps=LINK_CAPACITY_BPS,
                 max_age_s=DEFAULT_MAX_AGE_S):
        if capacity_bps <= 0:
            raise ValueError("capacity_bps must be positive")
        if max_age_s <= 0:
            raise ValueError("max_age_s must be positive")
        self.capacity_bps = float(capacity_bps)
        self.max_age_s = float(max_age_s)
        self._previous = {}
        self._utilization = {}
        self._updated_at = {}
        self._history = {}
        self._samples = {}

    @staticmethod
    def _is_tracked(dpid, port_no):
        return any((dpid, port_no) in ports
                   for ports in PATH_EGRESS_PORTS.values())

    def update_port(self, dpid, port_no, tx_bytes, now):
        """Update one port counter. The first sample establishes a baseline."""
        if not self._is_tracked(dpid, port_no):
            return
        if tx_bytes < 0:
            raise ValueError("tx_bytes must be non-negative")

        key = (dpid, port_no)
        previous = self._previous.get(key)
        self._previous[key] = (tx_bytes, now)
        if previous is None:
            return

        previous_bytes, previous_time = previous
        elapsed = now - previous_time
        delta_bytes = tx_bytes - previous_bytes
        if elapsed <= 0 or delta_bytes < 0:
            self._utilization.pop(key, None)
            self._updated_at.pop(key, None)
            self._history.pop(key, None)
            self._samples.pop(key, None)
            return

        rate_bps = (delta_bytes * 8.0) / elapsed
        utilization = min(rate_bps / self.capacity_bps, 1.0)
        history = self._history.setdefault(
            key, deque(maxlen=SAMPLES_PER_PORT)
        )
        history.append(utilization)
        samples = self._samples.setdefault(
            key, deque(maxlen=HISTORY_SAMPLES_PER_PORT)
        )
        samples.append((now, utilization))
        self._utilization[key] = utilization
        self._updated_at[key] = now

    def reset_datapath(self, dpid):
        """Discard samples when a switch disconnects or reconnects."""
        keys = [key for key in self._previous if key[0] == dpid]
        for key in keys:
            self._previous.pop(key, None)
            self._utilization.pop(key, None)
            self._updated_at.pop(key, None)
            self._history.pop(key, None)
            self._samples.pop(key, None)

    def _sample_at_or_before(self, key, cutoff):
        samples = self._samples.get(key, ())
        eligible = [(timestamp, value) for timestamp, value in samples
                    if timestamp <= cutoff]
        if not eligible:
            return None
        timestamp, value = eligible[-1]
        recent = [sample for sample_time, sample in eligible
                  if sample_time <= timestamp][-SAMPLES_PER_PORT:]
        variability = pstdev(recent) if len(recent) > 1 else 0.0
        return timestamp, value, variability

    def path_telemetry(self, now, *, delay_s=0.0, max_age_s=None):
        """Return both paths using samples no newer than now-delay_s.

        age_s records the actual age of each selected sample. A caller may
        extend max_age_s by the configured delay so delayed-but-intentionally
        retained samples remain available to the uncertainty-aware policy.
        """
        if delay_s < 0:
            raise ValueError("delay_s must be non-negative")
        age_limit = self.max_age_s if max_age_s is None else float(max_age_s)
        if age_limit <= 0:
            raise ValueError("max_age_s must be positive")
        cutoff = now - delay_s
        result = {}
        for path, ports in PATH_EGRESS_PORTS.items():
            selected = [self._sample_at_or_before(port, cutoff)
                        for port in ports]
            if any(sample is None for sample in selected):
                return None
            ages = [now - sample[0] for sample in selected]
            if any(age < 0 or age > age_limit for age in ages):
                return None
            result[path] = Telemetry(
                utilization=max(sample[1] for sample in selected),
                age_s=max(ages),
                variability=max(sample[2] for sample in selected),
            )
        return result
