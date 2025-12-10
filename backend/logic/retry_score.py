import json, os

# Path to event_type_stats.json
DATA_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data", "event_type_stats.json")
)

# Load event stats once
with open(DATA_PATH, "r", encoding="utf-8") as f:
    EVENT_STATS = json.load(f)


def compute_retry_score(event_type: str) -> int:
    """
    Convert retry_percentage → retry_score.
    Higher score = more instability.

    Thresholds:
        >50%  -> retry_score = 2
        >40%  -> retry_score = 1
        else  -> retry_score = 0
    """
    info = EVENT_STATS.get(event_type, {})
    rp = info.get("retry_percentage", 0)

    if rp > 50:
        return 2
    if rp > 40:
        return 1
    return 0
