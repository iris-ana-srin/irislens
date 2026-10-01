import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

HOST = "localhost"
PORT1 = 5050
PORT2 = 5051

#-----CAMERAMGMT-----
CAMERAS =   [
                # {"id": "cam1", "feed_url": 0},
                {"id": "cam2", "feed_url": "rtsp://192.168.173.201:554/live/0"},
                {"id": "cam3", "feed_url": "rtsp://admin:Kendall123@192.168.173.204:554/cam/realmonitor?channel=1&subtype=0"},
                {"id": "cam4", "feed_url": "rtsp://admin:Kendall123@192.168.173.222:554/cam/realmonitor?channel=1&subtype=0"},
            ]
DEFAULT_CAMERA_ID = CAMERAS[0]["id"]

CAMERA_WIDTH  = 640
CAMERA_HEIGHT = 480

STREAM_FPS = 30
JPEG_QUALITY = 75

#-----MQTT-----
MQTT_BROKER = "localhost"
MQTT_PORT   = 1883

REQUEST_TOPIC  = "irislens/reqs"
RESPONSE_TOPIC = "irislens/response"

#-----IDENTITY-----
SIM_THRESHOLD = 0.5
EMBEDDING_DIM = 512

CAPTURE_TIMEOUT = 1  # seconds

NUM_SAMPLES = 10
ENROLL_SIM_THRESHOLD = 0.5

DATA_DIR       = os.path.join(BASE_DIR, "identity/data")
AUDIT_LOG_PATH = os.path.join(BASE_DIR, "identity/logs/audit.log")

#frame quality filter thresholds
FRAME_MIN_LAPLACIAN  = 50.0
FRAME_MIN_BRIGHTNESS = 40.0
FRAME_MAX_BRIGHTNESS = 220.0

#liveness check threshold (applied to cropped face, after ArcFace)
LIVENESS_LAPLACIAN_THRESHOLD = 10

#-----SURVEILLANCE-----
VIDEO_DURATION = 10
VIDEO_FPS      = 20
PREBUFFER_SEC  = 5

SNAPSHOT_ROOT = "C:/FTP"
VIDEO_ROOT    = "C:/FTP"