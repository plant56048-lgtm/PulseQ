from __future__ import annotations
from ollama import chat
from datetime import datetime
from pathlib import Path
from threading import Lock
from uuid import uuid4

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
lock = Lock()
DATA_FILE = Path(__file__).parent / "data.json"

DOCTORS = {
    "Cardiology": ["Dr. Ananya Rao", "Dr. Vikram Shah"],
    "Orthopedics": ["Dr. Meera Iyer", "Dr. Arjun Nair"],
    "Neurology": ["Dr. Kavya Menon", "Dr. Rohan Das"],
    "General Medicine": ["Dr. Priya Kapoor", "Dr. Sameer Khan"],
    "Pediatrics": ["Dr. Neha Gupta", "Dr. Aditya Bose"],
}


def initial_state():
    return {
        "patient": {"name": "Maya Sharma", "token": "C-127", "appointment_id": "PQ-2026-127", "department": "Cardiology", "doctor": "Dr. Ananya Rao", "date": "2026-09-04", "time": "10:30 AM", "arrived": True},
        "queue": [
            {"token": "C-124", "name": "Aarav Patel", "status": "serving"},
            {"token": "C-125", "name": "Riya Singh", "status": "waiting"},
            {"token": "C-126", "name": "Dev Malhotra", "status": "waiting"},
            {"token": "C-127", "name": "Maya Sharma", "status": "waiting", "is_patient": True},
            {"token": "C-128", "name": "Ishaan Verma", "status": "waiting"},
        ],
        "doctor_status": "Consulting", "delay_minutes": 0, "average_minutes": 9,
        "emergencies": [],
        "notifications": [
            {"title": "Appointment confirmed", "message": "Your Cardiology appointment has been confirmed.", "time": "Just now", "kind": "success"},
            {"title": "Queue registered", "message": "You are checked in and have entered the queue.", "time": "Just now", "kind": "info"},
        ],
        "next_token": 129,
    }


def load_state():
    if not DATA_FILE.exists():
        save_state(initial_state())
    import json
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def save_state(state):
    import json
    DATA_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def notify(state, title, message, kind="info"):
    state["notifications"].insert(0, {"title": title, "message": message, "time": "Just now", "kind": kind})
    state["notifications"] = state["notifications"][:8]


def patient_queue_info(state):
    patient = state["patient"]
    index = next((i for i, item in enumerate(state["queue"]) if item["token"] == patient["token"]), None)
    if index is None:
        return {"position": None, "ahead": 0, "estimate": "Not yet in queue", "phase": "Appointment booked"}
    active = [x for x in state["queue"] if x["status"] in ("serving", "waiting")]
    index = next(i for i, item in enumerate(active) if item["token"] == patient["token"])
    ahead = index
    multiplier = {"Available": 0, "Consulting": 0, "Delayed": 15, "On Break": 20, "Unavailable": 30}.get(state["doctor_status"], 0)
    emergency_delay = 15 if any(e["status"] == "Accepted" for e in state["emergencies"]) else 0
    minutes = ahead * state["average_minutes"] + multiplier + state["delay_minutes"] + emergency_delay
    if active[index]["status"] == "serving":
        estimate, phase = "You are being consulted", "In consultation"
    elif ahead == 1:
        estimate, phase = "0–10 minutes", "Get ready"
    else:
        estimate, phase = f"{max(5, minutes - 5)}–{minutes + 5} minutes", "In queue"
    return {"position": index + 1, "ahead": ahead, "estimate": estimate, "phase": phase}


def public_state(state):
    info = patient_queue_info(state)
    queue = state["queue"]
    serving = next((x for x in queue if x["status"] == "serving"), None)
    waiting = [x for x in queue if x["status"] == "waiting"]
    return {**state, "patient_info": info, "serving": serving, "next_patients": waiting[:3], "queue_size": len(waiting) + (1 if serving else 0)}


@app.route("/")
def home():
    return render_template("index.html", doctors=DOCTORS)


@app.route("/api/state")
def get_state():
    with lock:
        return jsonify(public_state(load_state()))


@app.route("/api/book", methods=["POST"])
def book():
    payload = request.json
    with lock:
        state = load_state()
        token = f"C-{state['next_token']}"
        state["next_token"] += 1
        state["patient"].update({"name": payload["name"], "token": token, "appointment_id": f"PQ-{uuid4().hex[:6].upper()}", "department": payload["department"], "doctor": payload["doctor"], "date": payload["date"], "time": payload["time"], "arrived": False})
        state["queue"] = [x for x in state["queue"] if not x.get("is_patient")]
        notify(state, "Appointment confirmed", f"Your token {token} is ready. Check in when you arrive.", "success")
        save_state(state)
        return jsonify(public_state(state))


@app.route("/api/checkin", methods=["POST"])
def checkin():
    with lock:
        state = load_state(); p = state["patient"]
        if not any(x["token"] == p["token"] for x in state["queue"]):
            state["queue"].append({"token": p["token"], "name": p["name"], "status": "waiting", "is_patient": True})
        p["arrived"] = True
        notify(state, "You joined the queue", "Your token has been registered at the hospital.")
        save_state(state); return jsonify(public_state(state))


@app.route("/api/staff", methods=["POST"])
def staff_action():
    action = request.json.get("action")
    with lock:
        state = load_state(); queue = state["queue"]
        serving = next((x for x in queue if x["status"] == "serving"), None)
        if action == "call_next":
            if serving: serving["status"] = "done"
            nxt = next((x for x in queue if x["status"] == "waiting"), None)
            if nxt:
                nxt["status"] = "serving"
                if nxt.get("is_patient"): notify(state, "Your Turn", "You are next. Please proceed to the consultation room.", "urgent")
        elif action == "start":
            state["doctor_status"] = "Consulting"
        elif action == "finish":
            if serving: serving["status"] = "done"
            nxt = next((x for x in queue if x["status"] == "waiting"), None)
            if nxt:
                nxt["status"] = "serving"
                if nxt.get("is_patient"): notify(state, "Your Turn", "You are next. Please proceed to the consultation room.", "urgent")
            state["doctor_status"] = "Available"
        elif action == "absent" and serving:
            serving["status"] = "absent"
        elif action == "status":
            state["doctor_status"] = request.json["status"]
            if state["doctor_status"] == "Delayed": notify(state, "Doctor delayed", "Your estimated waiting time has been adjusted.", "warning")
        old = patient_queue_info(state)
        if old["phase"] == "Get ready": notify(state, "Get Ready", "Your appointment is approaching. Please be ready.", "warning")
        save_state(state); return jsonify(public_state(state))


@app.route("/api/walkin", methods=["POST"])
def walkin():
    p = request.json
    with lock:
        state = load_state(); token = f"C-{state['next_token']}"; state["next_token"] += 1
        state["queue"].append({"token": token, "name": p["name"], "status": "waiting"})
        save_state(state); return jsonify({"token": token, "state": public_state(state)})


@app.route("/api/emergency", methods=["POST"])
def emergency():
    p = request.json
    with lock:
        state = load_state()
        case = {"id": f"EM-{uuid4().hex[:5].upper()}", "time": datetime.now().strftime("%I:%M %p"), "name": p.get("name") or "Unknown", "location": p["location"], "problem": p["problem"], "conscious": p["conscious"], "status": "New"}
        state["emergencies"].insert(0, case)
        save_state(state); return jsonify(public_state(state))


@app.route("/api/emergency-status", methods=["POST"])
def emergency_status():
    p = request.json
    with lock:
        state = load_state()
        for case in state["emergencies"]:
            if case["id"] == p["id"]:
                case["status"] = p["status"]
                if p["status"] == "Accepted": notify(state, "Waiting time updated", "Your estimated waiting time has changed because the hospital is handling an emergency case.", "warning")
        save_state(state); return jsonify(public_state(state))


@app.route("/api/reset", methods=["POST"])
def reset():
    with lock:
        state = initial_state(); save_state(state); return jsonify(public_state(state))

@app.route("/api/queue-assistant", methods=["POST"])
def queue_assistant():
    with lock:
        state = load_state()
        info = patient_queue_info(state)

    prompt = f"""
You are PulseQ's hospital queue assistant.

Give a short, calm, non-medical explanation of the patient's queue update.
Never diagnose, provide treatment advice, or make promises.
Do not reveal any emergency patient's private details.

Current doctor status: {state["doctor_status"]}
Patients ahead: {info["ahead"]}
Estimated wait: {info["estimate"]}
Emergency handling active: {any(e["status"] == "Accepted" for e in state["emergencies"])}

Answer in 2 short sentences.
"""

    response = chat(
        model="llama3.2",
        messages=[{"role": "user", "content": prompt}],
    )

    return jsonify({"message": response.message.content})
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
