import pandas as pd
import json

# === Load dataset ===
df = pd.read_excel("Trusted_Notifications_Sample_Events_Updated.xlsx")
df.columns = [c.strip() for c in df.columns]


# === EVENT TYPES USED IN PROTOTYPE ===
SELECTED_EVENTS = {
    "OTP",
    "Transaction OTP",
    "Fraud Alert",
    "Monthly Statement",
    "Payment Confirmation"
}


# === MERGE EVENT TYPES ===
df["Event_Type"] = df["Event_Type"].replace({
    "Transaction OTP": "OTP"
})


# === NORMALIZE CHANNEL NAMES ===
CHANNEL_NORMALIZATION = {
    "Push Notification": "Push",
    "App Notification": "Push",
    "Mobile Push": "Push",

    "Email Notification": "Email",
    "E-mail": "Email",
    "Mail": "Email",

    "Whatsapp": "WhatsApp",
    "Whats app": "WhatsApp",

    "SMS ": "SMS",
    "sms": "SMS",
}

df["Intended_Channel"] = df["Intended_Channel"].replace(CHANNEL_NORMALIZATION)
df["Intended_Channel"] = df["Intended_Channel"].str.strip()   # Clean extra whitespace


# === FILTER FOR SELECTED EVENT TYPES ===
df = df[df["Event_Type"].isin(SELECTED_EVENTS)]


# === Compute stats ===
stats = {}

grouped = df.groupby(["Event_Type", "Intended_Channel"])

for (event_type, channel), group in grouped:
    total = len(group)
    failures = len(group[group["Delivered_YN"] == "N"])
    success = len(group[group["Delivered_YN"] == "Y"])

    failure_rate = failures / total if total else 0

    if event_type not in stats:
        stats[event_type] = {}

    stats[event_type][channel] = {
        "total_attempts": total,
        "failures": failures,
        "success": success,
        "failure_rate": round(failure_rate, 4)
    }


# === Save JSON ===
with open("channel_failure_stats.json", "w") as f:
    json.dump(stats, f, indent=4)

print("DONE! ---> Generated channel_failure_stats.json (merged + normalized)")
