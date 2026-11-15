"""Derive path utilization from OpenFlow port-transmit counters.

The two-path Mininet topology uses 100 Mbps links. We sample only the
inter-switch egress ports that distinguish the two candidate paths:
s1:2 + s2:2 for s1-s2-s4, and s1:3 + s3:2 for s1-s3-s4.
"""
from collections import deque
from statistics import pstdev

from controller.policies import Telemetry


# (datapath ID, egress port) pairs for the internal links on each path.
PATH_EGRESS_PORTS = {
    "s1-s2-s4": ((1, 2), (2, 2)),
    "s1-s3-s4": ((1, 3), (3, 2)),
}
LINK_CAPACITY_BPS = 100_000_000
SAMPLES_PER_PORT = 5
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
        # A non-positive interval or reset counter cannot yield a valid rate.
        if elapsed <= 0 or delta_bytes < 0:
            self._utilization.pop(key, None)
            self._updated_at.pop(key, None)
            self._history.pop(key, None)
            return

        rate_bps = (delta_bytes * 8.0) / elapsed
        utilization = min(rate_bps / self.capacity_bps, 1.0)
        history = self._history.setdefault(
            key, deque(maxlen=SAMPLES_PER_PORT)
        )
        history.append(utilization)
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

    def path_telemetry(self, now):
        """Return live telemetry for both paths, or None if either is stale.

        Path utilization is the maximum utilization of its two internal links,
        so a single congested hop is not hidden by averaging it with a lightly
        loaded hop. Variability is the largest population standard deviation
        across the recent per-link samples.
        """
        result = {}
        for path, ports in PATH_EGRESS_PORTS.items():
            if any(port not in self._utilization for port in ports):
                return None
            ages = [now - self._updated_at[port] for port in ports]
            if any(age < 0 or age > self.max_age_s for age in ages):
                return None
            variations = [
                pstdev(self._history[port])
                if len(self._history[port]) > 1 else 0.0
                for port in ports
            ]
            result[path] = Telemetry(
                utilization=max(self._utilization[port] for port in ports),
                age_s=max(ages),
                variability=max(variations),
            )
        return result
