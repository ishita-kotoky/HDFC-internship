import os
import json
import random
from functools import lru_cache
from typing import List, Dict, Optional

# Paths
DATA_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data"))
EVENT_STATS_PATH = os.path.join(DATA_DIR, "event_type_stats.json")
SAMPLE_EVENTS_PATH = os.path.join(DATA_DIR, "sampleEvents.json")  # your detailed sample events


def safe_load_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


@lru_cache(maxsize=1)
def load_event_stats() -> dict:
    return safe_load_json(EVENT_STATS_PATH)


@lru_cache(maxsize=1)
def load_sample_events() -> List[dict]:
    """
    sampleEvents.json expected to be an array of events with fields at least:
      - event_type
      - channel
      - status  (e.g. "SUCCESS"|"FAILED")
    """
    data = safe_load_json(SAMPLE_EVENTS_PATH)
    # If sampleEvents.json holds a dict with a key (e.g., "events"), try to handle gracefully
    if isinstance(data, dict) and "events" in data and isinstance(data["events"], list):
        return data["events"]
    if isinstance(data, list):
        return data
    return []


def compute_channel_reliability(event_type: str) -> Dict[str, float]:
    """
    Compute reliability = successCount / totalAttempts per channel for the given event_type.
    Returns a dict channel -> reliability (0.0 - 1.0). If no data, returns default 0.5 for channel.
    """
    events = load_sample_events()
    stats = {}  # {channel: {"success": X, "total": Y}}

    for e in events:
        # tolerant access
        et = e.get("event_type") or e.get("type") or e.get("event")
        ch = e.get("channel")
        status = e.get("status")
        if not et or not ch:
            continue
        if et != event_type:
            continue

        if ch not in stats:
            stats[ch] = {"success": 0, "total": 0}
        stats[ch]["total"] += 1
        if str(status).upper().startswith("SUC"):  # allow "SUCCESS"
            stats[ch]["success"] += 1

    # compute reliability
    reliabilities = {}
    for ch, d in stats.items():
        total = d["total"]
        reliabilities[ch] = (d["success"] / total) if total > 0 else 0.5

    return reliabilities


def rank_by_reliability(reliabilities: Dict[str, float], channels: List[str]) -> List[str]:
    """
    Given a mapping channel->reliability and a list of channels,
    returns channels sorted by descending reliability (most reliable first).
    Tie-breaker: alphabetical.
    If a channel has no measured reliability, default to 0.5.
    """
    items = [(ch, reliabilities.get(ch, 0.5)) for ch in channels]
    ordered = sorted(items, key=lambda x: (-x[1], x[0]))  # descending reliability
    return [ch for ch, _ in ordered]


def retry_score_to_failprob(score: int) -> float:
    """
    Mapping from retry score to failure probability as per your spec.
    Score -> failure probability
    0 -> 5%
    1 -> 15%
    2 -> 30%
    3 -> 55%
    4 -> 75%
    5 -> 90%
    Any >5 -> 0.95
    """
    mapping = {
        0: 0.05,
        1: 0.15,
        2: 0.30,
        3: 0.55,
        4: 0.75,
        5: 0.90
    }
    return mapping.get(score, 0.95)


def compute_routing_strategy(
    event_type: str,
    intended_channels: Optional[List[str]] = None,
    intended_channel_override: Optional[str] = None,
    force_final_fallback: str = "Inbox"
) -> Dict:
    
    event_stats = load_event_stats().get(event_type, {})
    allowed = event_stats.get("allowed_channels", [])  # hard rule
    if not allowed:
        # fallback: use any channels present in sample data for this event_type
        reliabilities = compute_channel_reliability(event_type)
        allowed = list(reliabilities.keys()) or ["Inbox", "Email", "SMS", "InApp", "WhatsApp"]

    # sanitize case/format (preserve provided names)
    allowed = [str(c) for c in allowed]

    # compute reliabilities for this event type
    reliabilities = compute_channel_reliability(event_type)

    # If intended_channels passed from event-level config, intersect with allowed
    if intended_channels:
        # ensure we only consider allowed channels
        intended_filtered = [c for c in intended_channels if c in allowed]
        if intended_filtered:
            allowed = intended_filtered

    # Determine primary
    # Rule: If an intended_channel_override is provided (e.g., request asked for whatsapp),
    #   - if it's allowed -> primary = intended_channel_override
    #   - else -> auto-correct (primary = most reliable allowed channel)
    if intended_channel_override:
        if intended_channel_override in allowed:
            primary = intended_channel_override
        else:
            # auto-correct to most reliable
            primary = rank_by_reliability(reliabilities, allowed)[0]
    else:
        # Default primary: business-defined first allowed channel (hard rule)
        primary = allowed[0]

    # Build fallback candidates (allowed minus primary)
    fallback_candidates = [c for c in allowed if c != primary]

    # Sort fallback candidates by reliability (most reliable first)
    fallback_sorted = rank_by_reliability(reliabilities, fallback_candidates)

    # Ensure final Inbox fallback is at the end
    if force_final_fallback:
        if force_final_fallback in fallback_sorted:
            fallback_sorted = [c for c in fallback_sorted if c != force_final_fallback] + [force_final_fallback]
        else:
            # If Inbox not in candidates, append it anyway (guaranteed final fallback)
            fallback_sorted.append(force_final_fallback)

    ranked_channels = [primary] + fallback_sorted

    # For completeness, include failure probabilities (1-reliability) as well as reliability
    failure_rates = {}
    for ch in ranked_channels:
        r = reliabilities.get(ch, None)
        if r is None:
            # if we don't have data, assume 0.5 reliability
            r = 0.5
        failure_rates[ch] = round(1.0 - float(r), 4)

    return {
        "primary": primary,
        "fallbacks": fallback_sorted,
        "ranked_channels": ranked_channels,
        "reliability": {ch: float(reliabilities.get(ch, 0.5)) for ch in ranked_channels},
        "failure_rates": failure_rates,
        "retry_score_to_failprob": retry_score_to_failprob  # helper exposed for caller convenience
    }

