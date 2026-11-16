"""Test-only path pinning helpers for controlled Mininet experiments."""

VALID_PATHS = ("s1-s2-s4", "s1-s3-s4")


def pinned_experiment_path(configured_path, destination_port, first_flow_port=5001):
    """Return a forced path only for the configured first-flow TCP destination port."""
    if configured_path in (None, ""):
        return None
    if configured_path not in VALID_PATHS:
        raise ValueError(
            f"experiment initial path must be one of {VALID_PATHS}, got {configured_path!r}"
        )
    if not isinstance(first_flow_port, int) or not 1 <= first_flow_port <= 65535:
        raise ValueError("experiment first-flow port must be an integer in [1,65535]")
    if destination_port is not None and (
        not isinstance(destination_port, int) or not 1 <= destination_port <= 65535
    ):
        raise ValueError("destination port must be an integer in [1,65535] or None")
    return configured_path if destination_port == first_flow_port else None
