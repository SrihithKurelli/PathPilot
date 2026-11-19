import socket
import threading
import time

from experiments.tcp_echo import run_client, serve


def test_tcp_echo_probe_collects_application_rtt_samples():
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    stop = threading.Event()
    server = threading.Thread(target=serve, args=("127.0.0.1", port, stop), daemon=True)
    server.start()
    try:
        time.sleep(.1)
        result = run_client("127.0.0.1", port, .25, 20)
    finally:
        stop.set()
        server.join(timeout=1)
    assert result["sent_requests"] >= 3
    assert len(result["rtt_samples"]) == result["sent_requests"]
    assert result["failed_requests"] == 0
    assert all(sample["rtt_ms"] >= 0 for sample in result["rtt_samples"])


def test_tcp_echo_probe_recovers_after_temporary_server_outage():
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    stop = threading.Event()
    result = None

    def delayed_server_start():
        time.sleep(.15)
        serve("127.0.0.1", port, stop)

    server = threading.Thread(target=delayed_server_start, daemon=True)
    server.start()
    try:
        result = run_client("127.0.0.1", port, .45, 20)
    finally:
        stop.set()
        server.join(timeout=1)
    assert result["failed_requests"] > 0
    assert result["successful_requests"] >= 2
    assert result["attempted_requests"] == (
        result["failed_requests"] + result["successful_requests"]
    )
    assert result["scheduled_requests"] == (
        result["attempted_requests"] + result["skipped_requests"]
    )
