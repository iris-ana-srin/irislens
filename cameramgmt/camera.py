#camera.py
import threading
import cv2

from config import CAMERA_WIDTH, CAMERA_HEIGHT, CAMERAS


class Camera:
    def __init__(self, camera_id: str, feed_url, width: int = CAMERA_WIDTH, height: int = CAMERA_HEIGHT):
        self.camera_id = camera_id
        self.feed_url  = feed_url
        self.width     = width
        self.height    = height
        self.cap: cv2.VideoCapture | None = None
        self.frame     = None
        self.running   = False
        self._thread: threading.Thread | None = None

    def start(self):
        if self.running:
            return
        print(f"[Camera:{self.camera_id}] Connecting …")
        self.cap = cv2.VideoCapture(self.feed_url)
        self.running = True
        self._thread = threading.Thread(target=self._update, daemon=True)
        self._thread.start()
        print(f"[Camera:{self.camera_id}] Connected.")

    def _update(self):
        while self.running:
            if self.cap is None:
                break
            ret, frame = self.cap.read()
            if ret:
                self.frame = frame

    def read(self):
        return self.frame

    def stop(self):
        self.running = False
        if self._thread is not None:
            self._thread.join()
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.frame = None
        print(f"[Camera:{self.camera_id}] Stopped.")


class CameraManager:
    """owns every configured Camera and routes."""

    def __init__(self, camera_configs: list[dict] = CAMERAS):
        self.cameras: dict[str, Camera] = {
            c["id"]: Camera(
                                camera_id=c["id"],
                                feed_url=c["feed_url"],
                                width=c.get("width", CAMERA_WIDTH),
                                height=c.get("height", CAMERA_HEIGHT),
                            )
            for c in camera_configs
        }

    def ids(self) -> list[str]:
        return list(self.cameras.keys())

    def get(self, camera_id: str) -> Camera | None:
        return self.cameras.get(camera_id)

    def read(self, camera_id: str):
        cam = self.get(camera_id)
        return cam.read() if cam else None

    def start_all(self):
        for cam in self.cameras.values():
            cam.start()

    def stop_all(self):
        for cam in self.cameras.values():
            cam.stop()