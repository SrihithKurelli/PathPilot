import json

from controller.event_ledger import EventLedger


def test_event_ledger_writes_timestamped_jsonl_and_counts(tmp_path):
    ticks = iter([10.0, 10.5, 11.0])
    ledger = EventLedger(tmp_path / "events.jsonl", clock=lambda: next(ticks))
    first = ledger.record("decision", path="s1-s2-s4", policy="least_loaded")
    ledger.record("flow_mod", command="add", estimated_bytes=128)
    assert first["elapsed_s"] == 0
    rows = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert [row["event"] for row in rows] == ["decision", "flow_mod"]
    assert rows[1]["elapsed_s"] == 1
    assert ledger.snapshot()["event_counts"] == {"decision": 1, "flow_mod": 1}


def test_event_ledger_without_file_is_still_counted():
    ledger = EventLedger()
    ledger.record("stats_request")
    assert ledger.snapshot()["event_counts"] == {"stats_request": 1}
