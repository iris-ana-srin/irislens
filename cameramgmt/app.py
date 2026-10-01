#app.py 
import time
import cv2
from flask import Flask, Response, jsonify, render_template

from cameramgmt.camera import CameraManager
from config import CAMERAS, STREAM_FPS, JPEG_QUALITY, HOST, PORT2

app = Flask(__name__)

cameras    = CameraManager(CAMERAS)
camera_ids = cameras.ids()
cameras.start_all()

_frame_interval = 1.0 / STREAM_FPS

def generate_frames(camera_id: str):
    while True:
        frame = cameras.read(camera_id)
        if frame is None:
            time.sleep(0.03)
            continue
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        if not ok:
            continue
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")
        time.sleep(_frame_interval)


@app.route("/stream/<camera_id>")
def stream(camera_id):
    if camera_id not in camera_ids:
        return jsonify({"error": f"unknown camera '{camera_id}'"}), 404
    return Response(generate_frames(camera_id), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/cameras")
def api_cameras():
    return jsonify([{"id": cid, "live": cameras.get(cid).is_live()} for cid in camera_ids ])


@app.route("/")
def index():
    return render_template("index.html", camera_ids=camera_ids)


if __name__ == "__main__":
    print(f"[CameraViewer] Starting on http://localhost:{PORT2}")
    for cid in camera_ids:
        print(f"[CameraViewer]   {cid} → http://localhost:{PORT2}/stream/{cid}")
    try:
        app.run(host=HOST, port=PORT2, threaded=True)
    except KeyboardInterrupt:
        pass
    finally:
        cameras.stop_all()