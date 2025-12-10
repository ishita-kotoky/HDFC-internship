from flask import Flask, render_template, request, jsonify
import uuid, json, os
import pytz
from datetime import datetime

# logic modules
from logic.simulate_channel import simulate_send
from logic.retry_score import compute_retry_score
from logic.routing_engine import compute_routing_strategy

app = Flask(__name__)

# -------------------------------------------------
# Paths
# -------------------------------------------------
BASE_DIR = os.path.dirname(__file__)
INBOX_PATH = os.path.join(BASE_DIR, "data", "inbox.json")
TRASH_PATH = os.path.join(BASE_DIR, "data", "trash.json")
EVENT_STATS_PATH = os.path.join(BASE_DIR, "data", "event_type_stats.json")

# -------------------------------------------------
# Load event-type stats
# -------------------------------------------------
with open(EVENT_STATS_PATH, "r", encoding="utf-8") as f:
    EVENT_STATS = json.load(f)

# -------------------------------------------------
# Helper functions for Inbox & Trash
# -------------------------------------------------
def load_inbox():
    try:
        with open(INBOX_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_inbox(data):
    with open(INBOX_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def save_to_inbox(notification):
    inbox = load_inbox()
    inbox.append({
        "notification_id": notification["notification_id"],
        "event_type": notification["event_type"],
        "delivered_via": notification["delivered_via"],
        "attempts": notification["attempts"],
        "timestamp": datetime.now(pytz.timezone("Asia/Kolkata")).isoformat()
    })
    save_inbox(inbox)

def load_trash():
    try:
        with open(TRASH_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_trash(data):
    with open(TRASH_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def save_to_trash(entry):
    trash = load_trash()
    trash.append(entry)
    save_trash(trash)

# -------------------------------------------------
# Routes
# -------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/inbox", methods=["GET"])
def inbox():
    return jsonify({"ok": True, "inbox": load_inbox()})

@app.route("/clear_inbox", methods=["POST"])
def clear_inbox():
    inbox = load_inbox()       # get all messages
    trash = load_trash()       # get existing trash

    # move all inbox items to trash
    trash.extend(inbox)
    save_trash(trash)

    # now clear inbox
    save_inbox([])

    return jsonify({"ok": True, "message": "Inbox cleared (moved to trash)"})


@app.route("/trash", methods=["GET"])
def trash():
    return jsonify({"ok": True, "trash": load_trash()})

@app.route("/empty_trash", methods=["POST"])
def empty_trash():
    save_trash([])
    return jsonify({"ok": True})

@app.route("/delete_message", methods=["POST"])
def delete_message():
    msg_id = request.json.get("notification_id")
    inbox = load_inbox()

    new_inbox = []
    deleted_entry = None

    for item in inbox:
        if item["notification_id"] == msg_id:
            deleted_entry = item
        else:
            new_inbox.append(item)

    save_inbox(new_inbox)

    if deleted_entry:
        save_to_trash(deleted_entry)

    return jsonify({"ok": True, "deleted": bool(deleted_entry)})

@app.route("/restore_message", methods=["POST"])
def restore_message():
    msg_id = request.json.get("notification_id")

    trash = load_trash()
    new_trash = []
    restored = None

    for item in trash:
        if item["notification_id"] == msg_id:
            restored = item
        else:
            new_trash.append(item)

    save_trash(new_trash)

    if restored:
        inbox = load_inbox()
        inbox.append(restored)
        save_inbox(inbox)

    return jsonify({"ok": True, "restored": bool(restored)})

# -------------------------------------------------
# SEND NOTIFICATION ENDPOINT
# -------------------------------------------------
@app.route("/send", methods=["POST"])
def send():
    payload = request.json or {}

    event_type = payload.get("event_type") or "OTP"
    demo_mode = payload.get("demo_mode")
    intended_channel_override = payload.get("intended_channel")

    event_info = EVENT_STATS.get(event_type, {})
    intended_channels_cfg = event_info.get("intended_channels", [])
    retry_percentage = event_info.get("retry_percentage", 0)

    retry_score = compute_retry_score(event_type)

    routing = compute_routing_strategy(
        event_type=event_type,
        intended_channels=intended_channels_cfg,
        intended_channel_override=intended_channel_override,
        force_final_fallback="Inbox"
    )

    primary = routing["primary"]
    fallbacks = routing["fallbacks"]
    ranked = routing["ranked_channels"]

    fail_prob_func = routing.get("retry_score_to_failprob")
    fail_prob = (
        fail_prob_func(retry_score)
        if callable(fail_prob_func)
        else (0.05 if retry_score == 0 else min(0.95, 0.15 * retry_score))
    )

    attempts = []
    delivered_channel = None

    # PRIMARY ATTEMPT
    if demo_mode == "force_primary_fail":
        primary_result = {
            "channel": primary,
            "status": "FAILED",
            "reason": "forced_primary_failure_demo_mode"
        }
    else:
        primary_result = simulate_send(primary, fail_prob)

    attempts.append(primary_result)

    if primary_result["status"] == "SUCCESS":
        delivered_channel = primary
    else:
        for ch in fallbacks:
            if ch.lower() == "inbox":
                continue

            fb_result = simulate_send(ch, fail_prob)
            attempts.append(fb_result)

            if fb_result["status"] == "SUCCESS":
                delivered_channel = ch
                break

        if delivered_channel is None:
            inbox_entry = {
                "channel": "Inbox",
                "status": "SUCCESS",
                "reason": "forced_final_fallback"
            }
            attempts.append(inbox_entry)
            delivered_channel = "Inbox"

    notification = {
        "notification_id": str(uuid.uuid4()),
        "event_type": event_type,
        "primary_channel": primary,
        "intended_channel_override": intended_channel_override,
        "retry_score": retry_score,
        "retry_percentage": retry_percentage,
        "routing_order": ranked,
        "delivered_via": delivered_channel,
        "attempts": attempts
    }

    save_to_inbox(notification)

    return jsonify({"ok": True, "notification": notification})

# -------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, port=5000)


