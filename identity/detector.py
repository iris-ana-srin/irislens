#detector.py
import os
from insightface.app import FaceAnalysis

class FaceDetector:
    def __init__(self, gpu: bool = True):
        self.app = FaceAnalysis(name="buffalo_l", root=os.path.dirname(os.path.abspath(__file__)))
        self.app.prepare(ctx_id=0 if gpu else -1)
        print(f"[FaceDetector] Loaded buffalo_l (gpu={gpu}).")

    def detect(self, frame) -> list:
        return self.app.get(frame)