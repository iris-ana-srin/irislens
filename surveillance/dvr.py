#dvr.py
import os
import sys
import time
import threading
from datetime import datetime
from collections import deque

import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mqttclient import MqttService

from cameramgmt.camera import CameraManager
from config import (CAMERAS, SNAPSHOT_ROOT, VIDEO_ROOT, VIDEO_FPS, VIDEO_DURATION, MQTT_BROKER, MQTT_PORT, REQUEST_TOPIC, RESPONSE_TOPIC, PREBUFFER_SEC)

cameras    = CameraManager(CAMERAS)
camera_ids = cameras.ids()

_prebuffers      = {cid: deque(maxlen=VIDEO_FPS * PREBUFFER_SEC) for cid in camera_ids}
_prebuffer_locks = {cid: threading.Lock() for cid in camera_ids}
_frame_events    = {cid: threading.Event() for cid in camera_ids}


def _prebuffer_feeder(camera_id: str):
    while True:
        frame = cameras.read(camera_id)
        if frame is not None:
            with _prebuffer_locks[camera_id]:
                _prebuffers[camera_id].append(frame)
            _frame_events[camera_id].set()
        time.sleep(1.0 / VIDEO_FPS)


def take_snapshot(camid: str):
    if camid not in camera_ids:
        print(f"[DVR] Unknown camid '{camid}' — ignoring snapshot request")
        return

    frame = cameras.read(camid)
    if frame is None:
        print(f"[DVR:{camid}] No frame available for snapshot")
        return

    out_dir = os.path.join(SNAPSHOT_ROOT, camid)
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(out_dir, f"{ts}.jpg")
    cv2.imwrite(path, frame)
    print(f"[DVR:{camid}] Snapshot saved → {path}")


def record_video(camid: str):
    print(f"[DVR:{camid}] Video recording triggered")

    out_dir = os.path.join(VIDEO_ROOT, camid)
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(out_dir, f"{ts}.mp4")

    frame = cameras.read(camid)
    if frame is None:
        print(f"[DVR:{camid}] No frame available for video")
        return
    h, w = frame.shape[:2]

    fourcc = cv2.VideoWriter_fourcc(*'avc1')
    writer = cv2.VideoWriter(path, fourcc, VIDEO_FPS, (w, h))

    with _prebuffer_locks[camid]:
        pre_frames = list(_prebuffers[camid])
    for f in pre_frames:
        writer.write(f)
    print(f"[DVR:{camid}] Prebuffer size:", len(pre_frames), "/ expected:", VIDEO_FPS * PREBUFFER_SEC)

    post_duration = VIDEO_DURATION - PREBUFFER_SEC
    end_time = time.time() + post_duration

    while time.time() < end_time:
        _frame_events[camid].wait(timeout=0.01)
        _frame_events[camid].clear()
        frame = cameras.read(camid)
        if frame is None:
            continue
        writer.write(frame)
    writer.release()
    print(f"[DVR:{camid}] Video saved → {path}")


#-------MQTT Handlers-------
#each handler receives (camid, value) 
def handle_snapshot(camid, value):
    if value is True:
        take_snapshot(camid)

def handle_record(camid, value):
    if value is True:
        threading.Thread(target=record_video, args=(camid,), daemon=True).start()


if __name__ == "__main__":
    cameras.start_all()
    for cid in camera_ids:
        threading.Thread(target=_prebuffer_feeder, args=(cid,), daemon=True).start()

    mqtt_service =   MqttService(
                                    broker          = MQTT_BROKER,
                                    port            = MQTT_PORT,
                                    request_topic   = REQUEST_TOPIC,
                                    response_topic  = RESPONSE_TOPIC,
                                    handlers        = { "snapreq":   handle_snapshot, "recordreq": handle_record},
                                )
    mqtt_service.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[DVR] Stopping...")
        cameras.stop_all()