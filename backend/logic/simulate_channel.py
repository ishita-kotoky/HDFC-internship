import random

def simulate_send(channel: str, fail_prob: float) -> dict:
    """
    Simulate an attempt to send via `channel` with a given failure probability (0.0 - 1.0).
    - Inbox is treated as guaranteed success (0% failure).
    - Returns a dict similar to your previous simulator for compatibility:
      {"channel": channel, "status": "SUCCESS"|"FAILED", "reason": "...", "fail_prob": <float>}
    """
    ch = str(channel)
    # Inbox is guaranteed successful
    if ch.lower() == "inbox":
        return {
            "channel": ch,
            "status": "SUCCESS",
            "reason": "inbox_forced_delivery",
            "fail_prob": 0.0
        }

    # clamp fail_prob
    try:
        fp = float(fail_prob)
    except Exception:
        fp = 0.5
    fp = max(0.0, min(1.0, fp))

    # simulate random outcome
    if random.random() < fp:
        return {
            "channel": ch,
            "status": "FAILED",
            "reason": f"simulated_failure (fail_prob={fp:.2f})",
            "fail_prob": fp
        }
    else:
        return {
            "channel": ch,
            "status": "SUCCESS",
            "reason": "delivered",
            "fail_prob": fp
        }
