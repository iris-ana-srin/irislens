#framefilter.py
import cv2
import numpy as np

from config import FRAME_MIN_LAPLACIAN, FRAME_MIN_BRIGHTNESS, FRAME_MAX_BRIGHTNESS

class FrameQualityFilter:
    def __init__(self, min_laplacian: float = FRAME_MIN_LAPLACIAN, min_brightness: float = FRAME_MIN_BRIGHTNESS, max_brightness: float = FRAME_MAX_BRIGHTNESS):
        self.min_laplacian = min_laplacian
        self.min_brightness = min_brightness
        self.max_brightness = max_brightness

    def check(self, frame) -> tuple[bool, str]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
        if sharpness < self.min_laplacian:
            return False, f"frame too blurry (sharpness={sharpness:.1f})"

        brightness = float(np.mean(gray))
        if brightness < self.min_brightness:
            return False, f"frame too dark (brightness={brightness:.1f})"
        if brightness > self.max_brightness:
            return False, f"frame too bright (brightness={brightness:.1f})"

        return True, ""