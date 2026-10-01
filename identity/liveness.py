#liveness.py
import cv2
import numpy as np

from config import LIVENESS_LAPLACIAN_THRESHOLD

class LivenessChecker:
    def __init__(self, threshold: float = LIVENESS_LAPLACIAN_THRESHOLD):
        self.threshold = threshold

    def check(self, frame, bbox: tuple[int, int, int, int]) -> bool:
        x1, y1, x2, y2 = bbox
        face_crop = frame[y1:y2, x1:x2]
        if face_crop.size == 0:
            return False
        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        lap  = cv2.Laplacian(gray, cv2.CV_64F).var()
        return lap >= self.threshold