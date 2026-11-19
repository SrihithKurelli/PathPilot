"""TCP request/echo probe for application-level end-to-end RTT samples."""
from __future__ import annotations
import argparse
import json
import math
import socket
import struct
import threading
import time
from pathlib import Path

FRAME = struct.Struct("!QQ")


def recv_exact(connection, size):
    chunks = bytearray()
    while len(chunks) < size:
        data = connection.recv(size - len(chunks))
        if not data:
            return None
        chunks.extend(data)
    return bytes(chunks)


def serve_connection(connection):
    with connection:
        connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        while True:
            frame = recv_exact(connection, FRAME.size)
            if frame is None:
                return
            connection.sendall(frame)


def serve(bind, port, stop_event=None):
    stop_event = stop_event or threading.Event()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((bind, port))
        server.listen(128)
        server.settimeout(.5)
        while not stop_event.is_set():
            try:
                connection, _ = server.accept()
            except socket.timeout:
                continue
            threading.Thread(target=serve_connection, args=(connection,), daemon=True).start()


def run_client(host, port, duration_s, rate_hz, *, connect_timeout=0.5,
               io_timeout=1.0):
    if duration_s <= 0 or rate_hz <= 0:
        raise ValueError("duration and rate must be positive")
    samples = []
    failure_reasons = {}
    start = time.monotonic()
    deadline = start + duration_s
    next_send = start
    sequence = 0
    attempted_requests = 0
    skipped_requests = 0
    connection = None
    interval = 1.0 / rate_hz
    while time.monotonic() < deadline:
        now = time.monotonic()
        if now < next_send:
            time.sleep(next_send - now)
        if time.monotonic() >= deadline:
            break
        sent_ns = time.monotonic_ns()
        attempted_requests += 1
        try:
            if connection is None:
                remaining = max(0.05, deadline - time.monotonic())
                connection = socket.create_connection(
                    (host, port), timeout=min(connect_timeout, remaining)
                )
                connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            connection.settimeout(min(io_timeout, max(.05, deadline - time.monotonic())))
            connection.sendall(FRAME.pack(sequence, sent_ns))
            echoed = recv_exact(connection, FRAME.size)
            received_ns = time.monotonic_ns()
            if echoed is None:
                raise ConnectionError("TCP echo server closed the connection")
            echoed_sequence, echoed_sent_ns = FRAME.unpack(echoed)
            if echoed_sequence != sequence or echoed_sent_ns != sent_ns:
                raise ValueError("echo response does not match request")
            samples.append({
                "sequence": sequence,
                "sent_monotonic_ns": sent_ns,
                "received_monotonic_ns": received_ns,
                "rtt_ms": (received_ns - sent_ns) / 1e6,
            })
        except OSError as exc:
            reason = type(exc).__name__
            failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
            if connection is not None:
                connection.close()
                connection = None
        sequence += 1
        next_send += interval
        now = time.monotonic()
        if next_send < now:
            overdue_slots = int((now - next_send) // interval) + 1
            remaining_slots = max(0, math.ceil((deadline - next_send) / interval))
            missed = min(overdue_slots, remaining_slots)
            skipped_requests += missed
            sequence += missed
            next_send += missed * interval
    if connection is not None:
        connection.close()
    return {
        "host": host, "port": port, "duration_s": duration_s,
        "offered_rate_hz": rate_hz,
        "sent_requests": len(samples),
        "attempted_requests": attempted_requests,
        "successful_requests": len(samples),
        "failed_requests": attempted_requests - len(samples),
        "skipped_requests": skipped_requests,
        "scheduled_requests": attempted_requests + skipped_requests,
        "failure_reasons": failure_reasons,
        "rtt_samples": samples,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    server = sub.add_parser("server")
    server.add_argument("--bind", default="0.0.0.0")
    server.add_argument("--port", type=int, default=5199)
    client = sub.add_parser("client")
    client.add_argument("--host", required=True)
    client.add_argument("--port", type=int, default=5199)
    client.add_argument("--duration", type=float, default=10)
    client.add_argument("--rate-hz", type=float, default=10)
    client.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "server":
        serve(args.bind, args.port)
    else:
        result = run_client(args.host, args.port, args.duration, args.rate_hz)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {len(result['rtt_samples'])} TCP application RTT samples to {args.output}")


if __name__ == "__main__":
    main()
