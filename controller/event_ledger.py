"""Thread-safe JSONL event ledger for controller and impairment evidence."""
from __future__ import annotations
import json
import os
import threading
import time
from pathlib import Path


class EventLedger:
    def __init__(self, path=None, clock=time.monotonic):
        self.path = Path(path).expanduser() if path else None
        self.clock = clock
        self.started = clock()
        self._lock = threading.Lock()
        self.counts = {}

    def record(self, event_type, **fields):
        now = self.clock()
        event = {
            "event": str(event_type),
            "monotonic_time": now,
            "elapsed_s": now - self.started,
            **fields,
        }
        with self._lock:
            self.counts[event_type] = self.counts.get(event_type, 0) + 1
            if self.path is not None:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
                try:
                    with os.fdopen(fd, "a", encoding="utf-8") as handle:
                        handle.write(json.dumps(event, sort_keys=True) + "\n")
                        handle.flush()
                        os.fsync(handle.fileno())
                except Exception:
                    # fdopen owns fd once constructed.
                    raise
        return event

    def snapshot(self):
        with self._lock:
            return {
                "event_counts": dict(self.counts),
                "event_log_path": str(self.path) if self.path is not None else "",
            }
