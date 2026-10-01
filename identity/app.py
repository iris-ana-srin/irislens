#app.py

import os
import sys
import json
import threading
import time
from datetime import datetime

import cv2
import numpy as np
from flask import Flask, Response, render_template, jsonify, request
from flask_sock import Sock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mqttclient import MqttService

from cameramgmt.camera      import CameraManager
from identity.pipeline      import MPipeline
from identity.database      import FaceDatabase
from identity.detector      import FaceDetector
from identity.auditlogger   import AuditLogger
from config import (CAMERAS, DEFAULT_CAMERA_ID,
                    HOST, PORT1,
                    SIM_THRESHOLD, CAPTURE_TIMEOUT, NUM_SAMPLES,
                    MQTT_BROKER, MQTT_PORT, REQUEST_TOPIC, RESPONSE_TOPIC)


app  = Flask(__name__)
sock = Sock(app)


cameras    = CameraManager(CAMERAS)
camera_ids = cameras.ids()

# Detector/DB/audit are safe and cheap to share; tracker/voter/smoother are NOT (see FacePipeline docstring) — each camera owns Pipeline.
db              = FaceDatabase()
shared_detector = FaceDetector(gpu=False)
shared_audit    = AuditLogger()

pipelines: dict[str, MPipeline] =   {
                                        cid: MPipeline(db=db, gpu=False, camera_id=cid, detector=shared_detector, audit=shared_audit)
                                        for cid in camera_ids
                                    }

cameras.start_all()

# ── Per-camera shared state ─────────────────────────────────────────────────
_ws_clients: set = set()
_ws_lock         = threading.Lock()

_scanning: dict[str, bool]                         = {cid: False for cid in camera_ids}
_scan_thread: dict[str, threading.Thread | None]    = {cid: None for cid in camera_ids}
_enrolling: dict[str, bool]                         = {cid: False for cid in camera_ids}
_enroll_thread: dict[str, threading.Thread | None]  = {cid: None for cid in camera_ids}

_frame_lock  = threading.Lock()
_latest_frame: dict[str, np.ndarray | None]  = {cid: None for cid in camera_ids}
_frame_event: dict[str, threading.Event]     = {cid: threading.Event() for cid in camera_ids}

def _frame_producer(cam_id: str):
    while True:
        frame = cameras.read(cam_id)
        if frame is not None:
            with _frame_lock:
                _latest_frame[cam_id] = frame
            _frame_event[cam_id].set()
        time.sleep(0.033)

for cid in camera_ids:
    threading.Thread(target=_frame_producer, args=(cid,), daemon=True).start()

def get_latest_frame(cam_id: str):
    with _frame_lock:
        return _latest_frame.get(cam_id)


# ── WebSocket broadcast ────────────────────────────────────────────────────
def broadcast(event: str, data: dict, camera_id: str | None = None):
    payload = dict(data)
    if camera_id is not None:
        payload["camera_id"] = camera_id
    msg = json.dumps({"event": event, "data": payload})
    dead = set()
    with _ws_lock:
        for ws in _ws_clients:
            try:
                ws.send(msg)
            except Exception:
                dead.add(ws)
        _ws_clients.difference_update(dead)


@sock.route("/ws")
def websocket(ws):
    with _ws_lock:
        _ws_clients.add(ws)
    try:
        while True:
            msg = ws.receive(timeout=30)
            if msg is None:
                break
            try:
                payload = json.loads(msg)
                if payload.get("action") == "ping":
                    broadcast("pong", {})
            except Exception:
                pass
    finally:
        with _ws_lock:
            _ws_clients.discard(ws)


# ── MJPEG stream (per camera) ───────────────────────────────────────────────
def generate_frames(cam_id: str):
    while True:
        frame = get_latest_frame(cam_id)
        if frame is None:
            time.sleep(0.03)
            continue
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")
        time.sleep(0.033)


@app.route("/stream/<camera_id>")
def stream(camera_id):
    if camera_id not in camera_ids:
        return jsonify({"error": f"unknown camera '{camera_id}'"}), 404
    return Response(generate_frames(camera_id), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/cameras")
def api_cameras():
    return jsonify([{"id": cid} for cid in camera_ids])


# ── Core scan logic (shared by Web UI and MQTT) ────────────────────────────
def _run_scan(camera_id: str, on_result=None):
    pipeline = pipelines[camera_id]

    best_score    = 0.0
    best_username = None
    best_password = None
    deadline      = time.time() + CAPTURE_TIMEOUT

    broadcast("scan_started", {"timeout": CAPTURE_TIMEOUT}, camera_id=camera_id)

    while _scanning[camera_id] and time.time() < deadline:
        _frame_event[camera_id].wait(timeout=0.1)
        _frame_event[camera_id].clear()
        frame = get_latest_frame(camera_id)
        if frame is None:
            continue

        result    = pipeline.process_frame(frame)
        remaining = max(0, int(deadline - time.time()))

        if result.frame_rejected:
            broadcast("scan_frame", {"remaining": remaining, "quality": "POOR", "reason": result.frame_reason, "tracks": []}, camera_id=camera_id)

        else:
            tracks_out = []
            for t in result.tracks:
                dec = t.decision
                tracks_out.append({
                                    "track_id": int(t.track_id), "bbox": [int(v) for v in t.bbox],
                                    "status": dec.status, "label": dec.label,
                                    "confidence": round(float(dec.confidence), 4), "liveness": bool(t.liveness_ok),
                                })
                if dec.status == "KNOWN" and dec.confidence > best_score:
                    best_score    = dec.confidence
                    best_username = str(dec.username)
                    best_password = dec.password

            broadcast("scan_frame", {"remaining": remaining, "quality": "OK", "tracks": tracks_out}, camera_id=camera_id)

            if best_score >= SIM_THRESHOLD:
                break

        time.sleep(0.04)
    _scanning[camera_id] = False

    status = "KNOWN" if best_score >= SIM_THRESHOLD else "UNKNOWN"
    result_payload =    {
                            "status":     status,
                            "username":   best_username if status == "KNOWN" else None,
                            # "password":   best_password if status == "KNOWN" else None,
                            "confidence": round(float(best_score), 4),
                            "camera_id":  camera_id,
                            "timestamp":  datetime.now().isoformat(),
                        }
    pipeline.log_session_result(status=status, username=result_payload["username"], confidence=result_payload["confidence"])
    broadcast("scan_result", result_payload, camera_id=camera_id)
    if on_result:
        on_result(result_payload)


def _start_scan(camera_id: str, on_result=None) -> tuple[bool, str]:
    if camera_id not in camera_ids:
        return False, f"unknown camera '{camera_id}'"
    if _scanning[camera_id]:
        return False, "scan already in progress"
    _scanning[camera_id] = True
    _scan_thread[camera_id] = threading.Thread(
        target=_run_scan, args=(camera_id,), kwargs={"on_result": on_result}, daemon=True)
    _scan_thread[camera_id].start()
    return True, "started"


# ── Web UI: login endpoints ────────────────────────────────────────────────
@app.route("/api/login", methods=["POST"])
def api_login():
    body      = request.get_json(silent=True) or {}
    camera_id = body.get("camera_id", DEFAULT_CAMERA_ID)
    ok, msg = _start_scan(camera_id)
    if not ok:
        return jsonify({"error": msg}), 409 if "progress" in msg else 400
    return jsonify({"status": msg, "camera_id": camera_id})


@app.route("/api/login/stop", methods=["POST"])
def api_login_stop():
    body      = request.get_json(silent=True) or {}
    camera_id = body.get("camera_id", DEFAULT_CAMERA_ID)
    if camera_id not in camera_ids:
        return jsonify({"error": f"unknown camera '{camera_id}'"}), 400
    _scanning[camera_id] = False
    broadcast("scan_aborted", {}, camera_id=camera_id)
    return jsonify({"status": "stopped", "camera_id": camera_id})


# ── People / DB (global — not per camera) ──────────────────────────────────
@app.route("/api/people", methods=["GET"])
def api_people_list():
    return jsonify(db.list_people())


@app.route("/api/people", methods=["POST"])
def api_people_enroll():
    body        = request.get_json(silent=True) or {}
    username    = body.get("username", "").strip()
    password    = body.get("password", "")
    num_samples = int(body.get("num_samples", NUM_SAMPLES))
    camera_id   = body.get("camera_id", DEFAULT_CAMERA_ID)

    if not username or not password:
        return jsonify({"error": "username and password required"}), 400
    if camera_id not in camera_ids:
        return jsonify({"error": f"unknown camera '{camera_id}'"}), 400
    if _enrolling[camera_id]:
        return jsonify({"error": "enrollment already in progress on this camera"}), 409

    _enrolling[camera_id]     = True
    _enroll_thread[camera_id] = threading.Thread(
        target=_run_enroll, args=(camera_id, username, password, num_samples), daemon=True)
    _enroll_thread[camera_id].start()
    return jsonify({"status": "started", "camera_id": camera_id})


@app.route("/api/people/<username>", methods=["DELETE"])
def api_people_delete(username):
    deleted = db.delete_person(username)
    if deleted:
        return jsonify({"deleted": deleted})
    return jsonify({"error": "not found"}), 404


MIN_FACE_SIZE = 80
MAX_SIMILAR   = 0.85

def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
    return float(np.dot(a, b))

def _is_diverse_enough(new_emb: np.ndarray, captured: list) -> bool:
    return all(_cosine_sim(new_emb, e) < MAX_SIMILAR for e in captured)

def _run_enroll(camera_id: str, username: str, password: str, num_samples: int):
    broadcast("enroll_started", {"username": username, "total": num_samples}, camera_id=camera_id)
    collected = 0
    captured  = []
    detector  = pipelines[camera_id].detector

    while collected < num_samples and _enrolling[camera_id]:
        _frame_event[camera_id].wait(timeout=0.1)
        _frame_event[camera_id].clear()
        frame = get_latest_frame(camera_id)
        if frame is None:
            continue

        faces = detector.detect(frame)
        if len(faces) != 1:
            broadcast("enroll_frame", {"collected": collected, "total": num_samples, "msg": "Need exactly 1 face"}, camera_id=camera_id)
            time.sleep(0.05)
            continue

        face = faces[0]
        x1, y1, x2, y2 = face.bbox.astype(int)
        if (x2 - x1) < MIN_FACE_SIZE:
            broadcast("enroll_frame", {"collected": collected, "total": num_samples, "msg": "Move closer"}, camera_id=camera_id)
            time.sleep(0.05)
            continue

        emb = face.embedding.astype("float32")
        if not _is_diverse_enough(emb, captured):
            broadcast("enroll_frame", {"collected": collected, "total": num_samples, "msg": "Hold still / vary pose slightly"}, camera_id=camera_id)
            time.sleep(0.05)
            continue

        captured.append(emb)
        db.add_embedding(emb, username, password)
        collected += 1
        broadcast("enroll_frame", {"collected": collected, "total": num_samples, "msg": f"Captured {collected}/{num_samples}"}, camera_id=camera_id)

    _enrolling[camera_id] = False
    if collected >= num_samples:
        broadcast("enroll_done", {"username": username, "samples": collected}, camera_id=camera_id)
    else:
        broadcast("enroll_cancelled", {"collected": collected}, camera_id=camera_id)


# ── Static / index ─────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html", camera_ids=camera_ids)


# ── MQTT integration ───────────────────────────────────────────────────────
def handle_login(camid, value):
    if value is True:
        _start_scan(camid, on_result=mqtt_publish_result)

def handle_qrscan(camid, value):
    print(f"[MQTT] QR scan requested for {camid}. Not implemented — ignoring.")

def mqtt_publish_result(result_payload: dict):
    camid       = result_payload["camera_id"]
    status_code = 1 if result_payload["status"] == "KNOWN" else 2
    for tag, val in (
                        ("frcurruser", result_payload["username"]),
                        # ("frcurrpass", result_payload["password"]),
                        ("confidence", result_payload["confidence"]),
                        ("frstatus",   status_code),
                    ):
        mqtt_service.publish_result({"camid": camid, "tagname": tag, "tagvalue": val})


if __name__ == "__main__":
    print(f"[FacialRecognition] Starting on http://localhost:{PORT1}")
    for cid in camera_ids:
        print(f"[FacialRecognition]   {cid} → http://localhost:{PORT1}/stream/{cid}")

    mqtt_service =  MqttService(
                                    broker=MQTT_BROKER, port=MQTT_PORT,
                                    request_topic=REQUEST_TOPIC, response_topic=RESPONSE_TOPIC,
                                    handlers={"loginreq":  handle_login},
                                )
    mqtt_service.start()
    app.run(host=HOST, port=PORT1, threaded=True)