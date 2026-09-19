"""
Mock SMS Gateway API
---------------------
A small FastAPI project simulating how an SMS/CPaaS gateway (like 2Factor)
handles sending messages, checking delivery status, and listing message logs.

This does NOT send real SMS — it simulates the behavior (async acceptance,
delivery status, common failure reasons) to demonstrate understanding of
how such APIs work.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from uuid import uuid4
import random

app = FastAPI(
    title="Mock SMS Gateway API",
    description="A simplified SMS sending/status/logs API, inspired by CPaaS platforms like 2Factor.",
    version="1.0.0",
)

# Allow the simple frontend (served from the same app) to call these endpoints freely
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory "database" — a simple Python dict standing in for a real DB.
# Key = message_id, Value = message record (dict)
# ---------------------------------------------------------------------------
messages_db = {}

# Possible failure reasons, used to simulate realistic outcomes
FAILURE_REASONS = ["DND_BLOCK", "INVALID_NUMBER", "DLT_TEMPLATE_MISMATCH", "CARRIER_ERROR"]


# ---------------------------------------------------------------------------
# Request/Response models (Pydantic) — define expected data shape + validation
# ---------------------------------------------------------------------------
class SMSRequest(BaseModel):
    phone_number: str = Field(..., example="9876543210", description="10-digit recipient phone number")
    message: str = Field(..., example="Your OTP is 4321", description="SMS text content")


class SMSResponse(BaseModel):
    message_id: str
    phone_number: str
    status: str
    timestamp: str


class StatusResponse(BaseModel):
    message_id: str
    phone_number: str
    status: str
    error_reason: str | None = None
    timestamp: str


# ---------------------------------------------------------------------------
# Helper function — simulates what a real telecom/carrier check might decide
# ---------------------------------------------------------------------------
def simulate_delivery_outcome():
    """Randomly decide delivered/failed, mimicking real-world carrier behavior."""
    if random.random() < 0.8:  # 80% chance of success, like a real gateway
        return "delivered", None
    else:
        return "failed", random.choice(FAILURE_REASONS)


# ---------------------------------------------------------------------------
# Endpoint 1: POST /send-sms
# Accepts a phone number + message, "queues" it, returns immediately (async-style)
# ---------------------------------------------------------------------------
@app.post("/send-sms", response_model=SMSResponse, status_code=202)
def send_sms(request: SMSRequest):
    # Basic validation beyond Pydantic's type checking
    if not request.phone_number.isdigit() or len(request.phone_number) != 10:
        raise HTTPException(status_code=422, detail="phone_number must be exactly 10 digits")

    message_id = str(uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    # Simulate the real outcome immediately for this mock (a real gateway
    # would do this asynchronously and notify via webhook/status endpoint)
    status, error_reason = simulate_delivery_outcome()

    messages_db[message_id] = {
        "message_id": message_id,
        "phone_number": request.phone_number,
        "message": request.message,
        "status": status,
        "error_reason": error_reason,
        "timestamp": timestamp,
    }

    # API responds quickly with "accepted" — mirrors real async SMS API behavior
    return SMSResponse(
        message_id=message_id,
        phone_number=request.phone_number,
        status="accepted",
        timestamp=timestamp,
    )


# ---------------------------------------------------------------------------
# Endpoint 2: GET /status/{message_id}
# Check the actual delivery outcome of a previously sent message
# ---------------------------------------------------------------------------
@app.get("/status/{message_id}", response_model=StatusResponse)
def get_status(message_id: str):
    record = messages_db.get(message_id)
    if not record:
        raise HTTPException(status_code=404, detail="message_id not found")

    return StatusResponse(
        message_id=record["message_id"],
        phone_number=record["phone_number"],
        status=record["status"],
        error_reason=record["error_reason"],
        timestamp=record["timestamp"],
    )


# ---------------------------------------------------------------------------
# Endpoint 3: GET /messages
# List all messages, with optional filtering by status (query parameter)
# Example: GET /messages?status=failed
# ---------------------------------------------------------------------------
@app.get("/messages")
def list_messages(status: str | None = None):
    all_messages = list(messages_db.values())

    if status:
        all_messages = [m for m in all_messages if m["status"] == status]

    return {"count": len(all_messages), "messages": all_messages}


# ---------------------------------------------------------------------------
# Root endpoint — simple health check
# ---------------------------------------------------------------------------
@app.get("/")
def root():
    return {"message": "Mock SMS Gateway API is running. Visit /docs for API docs, or /ui for a simple demo UI."}


# ---------------------------------------------------------------------------
# Simple demo UI — a single HTML page that calls the API above via fetch()
# This is just for demonstration; the real project is the API itself.
# ---------------------------------------------------------------------------
UI_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Mock SMS Gateway — Demo UI</title>
<style>
  body { font-family: Arial, sans-serif; max-width: 640px; margin: 40px auto; padding: 0 16px; color: #222; }
  h1 { font-size: 1.4rem; }
  .card { border: 1px solid #ddd; border-radius: 8px; padding: 20px; margin-bottom: 20px; }
  input, textarea { width: 100%; padding: 8px; margin: 6px 0 12px; box-sizing: border-box; border: 1px solid #ccc; border-radius: 4px; }
  button { background: #2563eb; color: white; border: none; padding: 10px 16px; border-radius: 4px; cursor: pointer; }
  button:hover { background: #1d4ed8; }
  pre { background: #f5f5f5; padding: 12px; border-radius: 6px; overflow-x: auto; font-size: 0.85rem; }
  .status-delivered { color: #15803d; font-weight: bold; }
  .status-failed { color: #b91c1c; font-weight: bold; }
  .status-accepted { color: #92400e; font-weight: bold; }
</style>
</head>
<body>
  <h1>📱 Mock SMS Gateway — Demo UI</h1>
  <p>A simple frontend for the SMS Gateway API. This just calls the same endpoints shown in <a href="/docs">/docs</a>.</p>

  <div class="card">
    <h3>Send SMS</h3>
    <label>Phone Number (10 digits)</label>
    <input id="phone" type="text" value="9876543210" maxlength="10">
    <label>Message</label>
    <textarea id="message" rows="2">Your OTP is 4321</textarea>
    <button onclick="sendSMS()">Send SMS</button>
    <pre id="sendResult">Response will appear here...</pre>
  </div>

  <div class="card">
    <h3>Check Delivery Status</h3>
    <label>Message ID</label>
    <input id="statusId" type="text" placeholder="Paste message_id here">
    <button onclick="checkStatus()">Check Status</button>
    <pre id="statusResult">Response will appear here...</pre>
  </div>

  <div class="card">
    <h3>All Messages</h3>
    <button onclick="loadMessages()">Refresh List</button>
    <div id="messagesList"></div>
  </div>

<script>
async function sendSMS() {
  const phone = document.getElementById('phone').value;
  const message = document.getElementById('message').value;
  const resultBox = document.getElementById('sendResult');
  resultBox.textContent = "Sending...";
  try {
    const res = await fetch('/send-sms', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone_number: phone, message: message })
    });
    const data = await res.json();
    resultBox.textContent = "Status: " + res.status + "\\n" + JSON.stringify(data, null, 2);
    if (data.message_id) {
      document.getElementById('statusId').value = data.message_id;
    }
    loadMessages();
  } catch (err) {
    resultBox.textContent = "Error: " + err;
  }
}

async function checkStatus() {
  const id = document.getElementById('statusId').value;
  const resultBox = document.getElementById('statusResult');
  if (!id) { resultBox.textContent = "Please enter a message_id first."; return; }
  resultBox.textContent = "Checking...";
  try {
    const res = await fetch('/status/' + id);
    const data = await res.json();
    resultBox.textContent = "Status: " + res.status + "\\n" + JSON.stringify(data, null, 2);
  } catch (err) {
    resultBox.textContent = "Error: " + err;
  }
}

async function loadMessages() {
  const listDiv = document.getElementById('messagesList');
  try {
    const res = await fetch('/messages');
    const data = await res.json();
    if (data.messages.length === 0) {
      listDiv.innerHTML = "<p>No messages sent yet.</p>";
      return;
    }
    listDiv.innerHTML = data.messages.map(m => {
      const cls = "status-" + m.status;
      return `<div style="border-top:1px solid #eee; padding:8px 0;">
        <b>${m.phone_number}</b> — <span class="${cls}">${m.status}</span>
        ${m.error_reason ? " (" + m.error_reason + ")" : ""}<br>
        <small>${m.message} · ${m.message_id}</small>
      </div>`;
    }).join("");
  } catch (err) {
    listDiv.textContent = "Error loading messages: " + err;
  }
}

// Load messages on page load
loadMessages();
</script>
</body>
</html>
"""


@app.get("/ui", response_class=HTMLResponse)
def demo_ui():
    return UI_HTML
