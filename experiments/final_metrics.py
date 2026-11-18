"""Proposal-aligned metric extraction for final PathPilot campaigns."""
from __future__ import annotations
import json, math, re, statistics
from collections import defaultdict

def _finite(values):
    xs=[float(v) for v in values]
    if any(not math.isfinite(v) for v in xs): raise ValueError("samples must be finite")
    return xs

def percentile(values, fraction):
    if not 0 <= fraction <= 1: raise ValueError("fraction must be in [0,1]")
    xs=sorted(_finite(values))
    if not xs: return ""
    p=(len(xs)-1)*fraction; lo=int(p); hi=min(lo+1,len(xs)-1)
    return xs[lo]*(1-(p-lo))+xs[hi]*(p-lo)

def jain_fairness(values):
    xs=_finite(values)
    if not xs: return ""
    if any(x<0 for x in xs): raise ValueError("throughputs must be non-negative")
    d=len(xs)*sum(x*x for x in xs)
    return 1.0 if d==0 else sum(xs)**2/d

def summarize_distribution(values,prefix):
    xs=_finite(values)
    names=("count","mean","std","p50","p95","p99","min","max")
    if not xs: return {f"{prefix}_{n}":"" for n in names}
    return {f"{prefix}_count":len(xs),f"{prefix}_mean":statistics.mean(xs),
      f"{prefix}_std":statistics.stdev(xs) if len(xs)>1 else 0.0,
      f"{prefix}_p50":percentile(xs,.5),f"{prefix}_p95":percentile(xs,.95),
      f"{prefix}_p99":percentile(xs,.99),f"{prefix}_min":min(xs),f"{prefix}_max":max(xs)}

def bootstrap_mean_ci(values,confidence=.95,resamples=4000,seed=7):
    xs=_finite(values)
    if not xs: return {"mean":"","ci_low":"","ci_high":"","n":0}
    if not 0<confidence<1 or resamples<100: raise ValueError("invalid CI parameters")
    import random
    rng=random.Random(seed)
    means=sorted(statistics.mean(rng.choices(xs,k=len(xs))) for _ in range(resamples))
    tail=(1-confidence)/2
    return {"mean":statistics.mean(xs),"ci_low":percentile(means,tail),
            "ci_high":percentile(means,1-tail),"n":len(xs)}

def path_stability(decisions,window_seconds,observation_duration_s=None):
    rows=sorted(decisions,key=lambda x:float(x["monotonic_time"]))
    if window_seconds<0: raise ValueError("window_seconds must be non-negative")
    changes=sum(a["path"]!=b["path"] for a,b in zip(rows,rows[1:]))
    reversals=sum(rows[i-2]["path"]==rows[i]["path"]!=rows[i-1]["path"]
      and float(rows[i]["monotonic_time"])-float(rows[i-2]["monotonic_time"])<=window_seconds
      for i in range(2,len(rows)))
    elapsed=(float(observation_duration_s) if observation_duration_s is not None else
             (float(rows[-1]["monotonic_time"])-float(rows[0]["monotonic_time"]) if len(rows)>1 else 0))
    return {"path_decisions":len(rows),"path_changes":changes,"path_reversals":reversals,
      "path_changes_per_minute":changes*60/elapsed if elapsed>0 else "",
      "reversal_window_seconds":window_seconds}

def settling_time(events,samples,utilization_threshold,hold_seconds,max_sample_gap_s=3.0):
    if not events: return ""
    if (not 0<=utilization_threshold<=1 or hold_seconds<0
            or max_sample_gap_s<=0):
        raise ValueError("invalid settling parameters")
    event=min(map(float,events)); points=sorted((float(x["monotonic_time"]),float(x["utilization"]))
      for x in samples if float(x["monotonic_time"])>=event)
    if not any(util > utilization_threshold for _, util in points):
        return ""
    start=None; previous=None
    for timestamp,util in points:
        if previous is not None and timestamp-previous>max_sample_gap_s:
            start=None
        if util<=utilization_threshold:
            if start is None: start=timestamp
            if timestamp-start>=hold_seconds: return start-event
        else: start=None
        previous=timestamp
    return ""

def _iperf_payload(payload):
    return json.loads(payload) if isinstance(payload, str) else payload


def _server_report(data):
    raw = data.get("server_output_json")
    if not raw:
        return {}
    try:
        return json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, json.JSONDecodeError):
        return {}


def _duration(summary):
    if not isinstance(summary, dict):
        return ""
    start, end = summary.get("start"), summary.get("end")
    if isinstance(start, (int, float)) and isinstance(end, (int, float)) and end > start:
        return float(end) - float(start)
    return ""


def parse_iperf3_json(payload):
    """Extract sender and receiver measurements without conflating their clocks.

    For TCP, prefer the server's receiver report when iperf3 supplied it.
    The sender and receiver may finish at different times in an emulated
    network with queued packets; that difference is retained, not rejected.
    """
    data = _iperf_payload(payload)
    end = data.get("end", {})
    protocol = data.get("start", {}).get("test_start", {}).get("protocol", "")
    server = _server_report(data)
    server_end = server.get("end", {})
    sent = end.get("sum_sent", {})
    client_received = end.get("sum_received", {})
    if protocol == "TCP":
        received = server_end.get("sum_received") or client_received
        if not received:
            received = server_end.get("sum") or end.get("sum", {})
        sender_rate = sent.get("bits_per_second", "")
        receiver_rate = received.get("bits_per_second", "") if received else ""
        sender_bytes = sent.get("bytes", "")
        receiver_bytes = received.get("bytes", "") if received else ""
        udp = {}
    else:
        # UDP receiver statistics are authoritative on the server. The client
        # summary can contain a different packet denominator, so prefer the
        # one-off server's receiver report when available.
        received = (server_end.get("sum_received") or server_end.get("sum")
                    or end.get("sum", {}))
        sender_rate = ""
        receiver_rate = received.get("bits_per_second", "") if received else ""
        sender_bytes = ""
        receiver_bytes = received.get("bytes", "") if received else ""
        udp = received

    packets = udp.get("packets")
    lost = udp.get("lost_packets")
    receiver_mbps = (float(receiver_rate) / 1e6
                     if isinstance(receiver_rate, (int, float)) else "")
    return {
        "iperf3_protocol": protocol,
        "sender_goodput_mbps": (float(sender_rate) / 1e6
                                if isinstance(sender_rate, (int, float)) else ""),
        "receiver_goodput_mbps": receiver_mbps,
        # Compatibility fields used by existing campaign analysis.
        "goodput_mbps": receiver_mbps,
        "sender_bytes": sender_bytes,
        "receiver_bytes": receiver_bytes,
        "bytes_received": receiver_bytes,
        "sender_duration_s": _duration(sent),
        "receiver_duration_s": _duration(received),
        "tcp_retransmits": sent.get("retransmits", ""),
        "udp_packets": packets if protocol == "UDP" else "",
        "udp_lost_packets": lost if protocol == "UDP" else "",
        "udp_loss_pct": (100 * lost / packets
                         if protocol == "UDP" and isinstance(packets, (int, float))
                         and packets > 0 and isinstance(lost, (int, float)) else ""),
        "udp_jitter_ms": udp.get("jitter_ms", "") if protocol == "UDP" else "",
        "receiver_report_source": (
            "server" if (
                (protocol == "TCP" and server_end.get("sum_received")) or
                (protocol == "UDP" and (
                    server_end.get("sum_received") or server_end.get("sum")
                ))
            ) else "client"
        ),
    }


def parse_iperf3_intervals(payload, flow_id):
    """Return per-second receiver-goodput samples for concurrent fairness windows."""
    data = _iperf_payload(payload)
    protocol = data.get("start", {}).get("test_start", {}).get("protocol", "")
    interval_source = data
    if protocol in {"TCP", "UDP"}:
        server = _server_report(data)
        if server.get("intervals"):
            interval_source = server
    records = []
    for index, interval in enumerate(interval_source.get("intervals", [])):
        summary = interval.get("sum", {})
        rate = summary.get("bits_per_second")
        if rate is None:
            continue
        records.append({
            "flow_id": flow_id,
            "window_id": index,
            "start_s": summary.get("start", index),
            "end_s": summary.get("end", index + 1),
            "goodput_mbps": float(rate) / 1e6,
        })
    return records

def parse_ss_tcp_rtt(text):
    return [float(x) for x in re.findall(r"\brtt:([0-9]+(?:\.[0-9]+)?)/",text)]

def parse_tc_qdisc_stats(text):
    def val(pattern):
        m=re.search(pattern,text); return int(m.group(1)) if m else ""
    return {"qdisc_packets":val(r"Sent \d+ bytes (\d+) pkt"),
      "qdisc_drops":val(r"dropped (\d+)"),"qdisc_overlimits":val(r" overlimits (\d+)"),
      "qdisc_backlog_bytes":val(r" backlog (\d+)b"),"qdisc_backlog_packets":val(r" backlog \d+b (\d+)p")}

def parse_ovs_port_stats(text):
    """Parse ovs-ofctl dump-ports counters; absent counters remain absent."""
    rows=[]; current=None
    for line in text.splitlines():
        header=re.search(r"(?:port\s+)?(\d+)(?:\([^)]*\))?:",line)
        if header:
            if current: rows.append(current)
            current={"port":int(header.group(1))}
        if current:
            direction=re.search(r"\b(rx|tx) pkts=(\d+), bytes=(\d+), drop(?:ped)?=(\d+), errs=(\d+)",line)
            if direction:
                prefix=direction.group(1)
                for suffix,value in zip(("packets","bytes","dropped","errors"),direction.groups()[1:]):
                    current[f"{prefix}_{suffix}"]=int(value)
    if current: rows.append(current)
    return rows

def aggregate_concurrent_flow_fairness(records, minimum_flows=2):
    """Compute Jain fairness over distinct flows in overlapping time windows."""
    if minimum_flows < 2:
        raise ValueError("minimum_flows must be at least two")
    grouped=defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
    for index, row in enumerate(records):
        window = row["window_id"]
        flow_id = row.get("flow_id", f"row-{index}")
        weight = float(row.get("overlap_seconds", 1.0))
        if weight <= 0:
            continue
        bucket = grouped[window][flow_id]
        bucket[0] += float(row["goodput_mbps"]) * weight
        bucket[1] += weight
    result = {}
    for window, flows in grouped.items():
        values = [total / duration for total, duration in flows.values() if duration > 0]
        if len(values) >= minimum_flows:
            result[window] = jain_fairness(values)
    return result
