"""Runtime metric helpers for Mininet/Ryu evaluation.

Linux /proc sampling is intentionally best-effort: unavailable process data is
reported as empty values rather than being fabricated. This module does not
claim to measure per-flow latency or packet loss.
"""
from __future__ import annotations

import math
import threading
import time
from pathlib import Path


def jain_fairness(values):
    """Return Jain's fairness index for non-negative per-flow throughputs."""
    numbers = [float(value) for value in values]
    if not numbers:
        return ""
    if any(not math.isfinite(value) or value < 0 for value in numbers):
        raise ValueError("throughputs must be finite and non-negative")
    denominator = len(numbers) * sum(value * value for value in numbers)
    if denominator == 0:
        return 1.0
    return (sum(numbers) ** 2) / denominator


def percentile(values, fraction):
    """Linearly interpolated percentile, with fraction in [0, 1]."""
    if not 0 <= fraction <= 1:
        raise ValueError("fraction must be in [0, 1]")
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return ""
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def path_transition_metrics(paths):
    """Count route changes and immediate A->B->A reversals in decision order."""
    decisions = list(paths)
    changes = sum(left != right for left, right in zip(decisions, decisions[1:]))
    reversals = sum(
        decisions[index] == decisions[index + 2]
        and decisions[index] != decisions[index + 1]
        for index in range(max(0, len(decisions) - 2))
    )
    return {"path_decision_count": len(decisions),
            "path_changes": changes, "path_reversals": reversals}


class ProcessMetricsSampler:
    """Sample one Linux process's CPU time and peak resident memory."""

    def __init__(self, pid, interval_s=0.25):
        self.pid = int(pid)
        self.interval_s = float(interval_s)
        self._stop = threading.Event()
        self._thread = None
        self._start_wall = None
        self._start_cpu = None
        self._peak_rss_kb = 0
        self._result = None

    def _read(self):
        stat = Path(f"/proc/{self.pid}/stat").read_text()
        # comm may contain spaces and parentheses; fields after the final ')'
        # begin with field 3. utime/stime are fields 14 and 15.
        fields = stat[stat.rfind(")") + 2:].split()
        ticks = int(fields[11]) + int(fields[12])
        try:
            status = Path(f"/proc/{self.pid}/status").read_text()
            rss_line = next(line for line in status.splitlines()
                            if line.startswith("VmRSS:"))
            rss_kb = int(rss_line.split()[1])
        except (OSError, StopIteration, ValueError, IndexError):
            rss_kb = 0
        return ticks, rss_kb

    def start(self):
        try:
            ticks, rss = self._read()
        except (OSError, ValueError, IndexError):
            return self
        self._start_wall = time.monotonic()
        self._start_cpu = ticks
        self._peak_rss_kb = rss
        self._thread = threading.Thread(target=self._sample, daemon=True)
        self._thread.start()
        return self

    def _sample(self):
        while not self._stop.wait(self.interval_s):
            try:
                _, rss = self._read()
            except (OSError, ValueError, IndexError):
                continue
            self._peak_rss_kb = max(self._peak_rss_kb, rss)

    def stop(self):
        # The trial harness may request metrics more than once while cleaning
        # up. Freeze the first completed snapshot so elapsed time cannot grow
        # and make the reported mean CPU percentage artificially decrease.
        if self._result is not None:
            return dict(self._result)
        if self._thread is None:
            self._result = {
                "controller_cpu_seconds": "",
                "controller_cpu_percent_mean": "",
                "controller_rss_peak_mb": "",
            }
            return dict(self._result)
        self._stop.set()
        self._thread.join(timeout=max(1.0, self.interval_s * 4))
        try:
            final_ticks, rss = self._read()
            self._peak_rss_kb = max(self._peak_rss_kb, rss)
        except (OSError, ValueError, IndexError):
            final_ticks = self._start_cpu
        wall = max(time.monotonic() - self._start_wall, 1e-9)
        import os
        hz = float(os.sysconf("SC_CLK_TCK"))
        cpu_seconds = max(0.0, (final_ticks - self._start_cpu) / hz)
        self._result = {
            "controller_cpu_seconds": round(cpu_seconds, 6),
            "controller_cpu_percent_mean": round(100.0 * cpu_seconds / wall, 4),
            "controller_rss_peak_mb": round(self._peak_rss_kb / 1024.0, 4),
        }
        return dict(self._result)
