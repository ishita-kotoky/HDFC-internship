/* ---------------------------------------------------
   ICONS + HELPERS 
--------------------------------------------------- */

function icon(channel) {
    switch ((channel || "").toLowerCase()) {
        case "sms": return "📩";
        case "email": return "📧";
        case "push": return "📱";
        case "whatsapp": return "💬";
        case "inbox": return "📥";
        default: return "🔔";
    }
}

function readableReason(r) {
    if (!r) return "";
    if (r.includes("forced_final_fallback"))
        return "Delivered via final fallback (Inbox) because all channels failed.";
    if (r.includes("retry_score"))
        return "Delivery failed due to high retry score.";
    return r.replace(/_/g, " ");
}

function eventTitle(eventType) {
    switch (eventType) {
        case "OTP": return "One-Time Passcode";
        case "Transaction OTP": return "Transaction Verification";
        case "Fraud Alert": return "Security Alert";
        case "Monthly Statement": return "Your Monthly Statement";
        case "Payment Confirmation": return "Payment Confirmation";
        default: return eventType;
    }
}

function eventDescription(eventType) {
    switch (eventType) {
        case "OTP": 
            return "Your OTP could not be delivered via SMS/Email and has been securely placed here.";
        case "Transaction OTP":
            return "We could not deliver your verification code. Please retrieve it from your Secure Inbox.";
        case "Fraud Alert":
            return "We attempted to notify you about a suspicious transaction. View this alert securely.";
        case "Monthly Statement":
            return "Your latest account statement is now available.";
        case "Payment Confirmation":
            return "Your payment confirmation has been delivered securely.";
        default:
            return "A new message has been delivered to your Secure Inbox.";
    }
}

function eventIcon(type) {
    switch (type) {
        case "OTP": 
        case "Transaction OTP": return "🔐";
        case "Fraud Alert": return "⚠️";
        case "Monthly Statement": return "📄";
        case "Payment Confirmation": return "💳";
        default: return "📩";
    }
}

function getDateGroup(timestamp) {
    const d = new Date(timestamp);
    const today = new Date();
    
    const diff = today.setHours(0,0,0,0) - d.setHours(0,0,0,0);

    if (diff === 0) return "Today";
    if (diff === 86400000) return "Yesterday";
    return "Earlier";
}

function renderInboxCard(msg) {
    return `
        <div class="secure-msg-card">
            <div class="msg-header">
                <span class="msg-icon">${eventIcon(msg.event_type)}</span>
                <span class="msg-title">${eventTitle(msg.event_type)}</span>
            </div>

            <div class="msg-description">${eventDescription(msg.event_type)}</div>

            <div class="msg-meta">
                <span class="msg-date">${new Date(msg.timestamp).toLocaleString()}</span>
                <span class="msg-badge">Secure Inbox</span>
            </div>
        </div>
    `;
}

/* ---------------------------------------------------
   TOAST
--------------------------------------------------- */

function showToast(message, type = "success") {
    const toast = document.getElementById("toast");
    toast.textContent = message;

    toast.style.background = type === "error" ? "#e74c3c" : "#4c44d6";

    toast.classList.add("show");

    setTimeout(() => toast.classList.remove("show"), 2500);
}

/* ---------------------------------------------------
   TOP NAVIGATION TAB SWITCHING
--------------------------------------------------- */

const tabs = document.querySelectorAll(".nav-tab");
const contents = document.querySelectorAll(".tab-content");

tabs.forEach((btn) => {
    btn.addEventListener("click", () => {
        let tab = btn.getAttribute("data-tab");

        // Remove "active" from all nav buttons
        tabs.forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");

        // Hide all sections
        contents.forEach((c) => {
            c.style.display = "none";
            c.classList.remove("active");
        });

        // Show the selected section
        const selected = document.getElementById(tab);
        selected.style.display = "block";
        selected.classList.add("active");
    });
});

// Activate first tab on load
document.addEventListener("DOMContentLoaded", () => {
    const first = document.querySelector(".nav-tab");
    if (first) first.click();
});

/* ---------------------------------------------------
   METADATA PANEL TOGGLE
--------------------------------------------------- */

document.getElementById("toggleMetadataBtn").addEventListener("click", () => {
    const panel = document.getElementById("metadataPanel");
    const btn = document.getElementById("toggleMetadataBtn");

    const isHidden = panel.style.display === "none" || panel.style.display === "";
    panel.style.display = isHidden ? "block" : "none";
    btn.textContent = isHidden ? "Hide" : "Show";
});

/* ---------------------------------------------------
   SEND NOTIFICATION
--------------------------------------------------- */

document.getElementById("sendBtn").addEventListener("click", async () => {
    const eventType = document.getElementById("eventType").value;
    const responseBox = document.getElementById("responseBox");

    const primaryEl = document.getElementById("primaryChannel");
    const retryScoreEl = document.getElementById("retryScore");
    const retryPercentEl = document.getElementById("retryPercent");

    const demoEnabled = document.getElementById("demoToggle").checked;

    responseBox.textContent = "Sending...";

    try {
        const res = await fetch("/send", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                event_type: eventType,
                demo_mode: demoEnabled ? "force_primary_fail" : null
            })
        });

        const json = await res.json();
        responseBox.textContent = JSON.stringify(json, null, 2);

        showToast("Notification sent successfully!");

        if (json.notification) {
            primaryEl.textContent = icon(json.notification.primary_channel) + 
                                    " " + json.notification.primary_channel;

            retryScoreEl.textContent = json.notification.retry_score;
            retryPercentEl.textContent = json.notification.retry_percentage + "%";

            document.getElementById("metadataPanel").style.display = "block";
            document.getElementById("toggleMetadataBtn").textContent = "Hide";
        }

        /* RENDER TIMELINE */
        if (json.notification?.attempts) {
            const attempts = json.notification.attempts;
            let html = "";

            attempts.forEach((a, i) => {
                const color = a.status === "SUCCESS" ? "green" : "red";

                html += `
                    <div style="
                        margin-bottom:10px;
                        padding:12px;
                        border-left:4px solid ${color};
                        background:#fff;
                        border-radius:8px;
                        font-size:14px;
                    ">
                        <div style="font-weight:bold; color:${color}">
                            ${icon(a.channel)} Attempt ${i+1} — ${a.channel}: ${a.status}
                        </div>
                        <div style="opacity:0.75; margin-top:4px;">
                            ${readableReason(a.reason)}
                        </div>
                    </div>
                `;
            });

            document.getElementById("attemptsBox").innerHTML = html;
        }

    } catch (err) {
        responseBox.textContent = "Error: " + err.message;
        showToast("Failed to send notification", "error");
    }
});

/* ---------------------------------------------------
   INBOX + SEARCH
--------------------------------------------------- */

document.getElementById("loadInboxBtn").addEventListener("click", loadInbox);
document.getElementById("searchInbox").addEventListener("input", loadInbox);

document.getElementById("clearInboxBtn").addEventListener("click", async () => {
    await fetch("/clear_inbox", { method: "POST" });
    document.getElementById("inboxBox").innerHTML = "<p>Inbox cleared.</p>";
});

async function loadInbox() {
    const inboxBox = document.getElementById("inboxBox");
    const query = document.getElementById("searchInbox").value.toLowerCase();

    inboxBox.innerHTML = `
        <div style="padding:20px; text-align:center; opacity:0.7;">
            Loading Secure Inbox...
        </div>
    `;

    const res = await fetch("/inbox");
    const json = await res.json();
    let inbox = json.inbox || [];

    // Sort newest → oldest
    inbox.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

    // Search filter
    if (query) {
        inbox = inbox.filter(msg =>
            msg.event_type.toLowerCase().includes(query)
        );
    }

    // Group inbox
    const groups = { Today: [], Yesterday: [], Earlier: [] };
    inbox.forEach(msg => groups[getDateGroup(msg.timestamp)].push(msg));

    // Render
    let html = "";
    for (const group of ["Today", "Yesterday", "Earlier"]) {
        if (groups[group].length === 0) continue;
        html += `<h3 class="group-title">${group}</h3>`;
        groups[group].forEach(msg => html += renderInboxCard(msg));
    }

    inboxBox.innerHTML = html || "<p>No messages found.</p>";
}

/* ---------------------------------------------------
   TRASH
--------------------------------------------------- */

document.getElementById("loadTrashBtn").addEventListener("click", loadTrash);
document.getElementById("emptyTrashBtn").addEventListener("click", emptyTrash);

async function loadTrash() {
    const trashBox = document.getElementById("trashBox");
    trashBox.innerHTML = "Loading trash...";

    const res = await fetch("/trash");
    const json = await res.json();

    let html = "";
    json.trash.forEach(msg => {
        html += `
            <div class="secure-msg-card">
                <div class="msg-header">🗑️ Deleted: ${msg.event_type}</div>

                <div class="msg-description">
                    Originally delivered via: ${msg.delivered_via}
                </div>

                <button class="primary-btn" onclick="restoreMessage('${msg.notification_id}')">
                    ♻️ Restore
                </button>
            </div>
        `;
    });

    trashBox.innerHTML = html || "(Trash Empty)";
}

async function restoreMessage(id) {
    await fetch("/restore_message", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ notification_id: id })
    });

    showToast("Message restored!");
    loadTrash();
}

async function emptyTrash() {
    await fetch("/empty_trash", { method: "POST" });
    showToast("Trash emptied!");
    document.getElementById("trashBox").innerHTML = "(Trash Empty)";
}
