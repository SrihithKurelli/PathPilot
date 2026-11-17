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
    assert all(sample["rtt_ms"] >= 0 for sample in result["rtt_samples"])
