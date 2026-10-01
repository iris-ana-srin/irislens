#tracker.py
import numpy as np
from identity.sort import Sort

class FaceTracker:
    def __init__(self, max_age: int = 5, min_hits: int = 1, iou_threshold: float = 0.3):
        self.tracker = Sort(max_age=max_age, min_hits=min_hits, iou_threshold=iou_threshold)

    def update(self, faces: list) -> list:
        if not faces:
            self.tracker.update(np.empty((0, 5)))
            return []

        bboxes = np.array([f.bbox.astype(float) for f in faces])
        scores = np.ones((len(bboxes), 1))          
        dets   = np.hstack((bboxes, scores))        

        tracked = self.tracker.update(dets)         

        results = []
        for t in tracked:
            x1, y1, x2, y2, track_id = t.astype(int)

            best_face, best_iou = None, 0.0
            for face in faces:
                fx1, fy1, fx2, fy2 = face.bbox.astype(int)
                ix1, iy1 = max(x1, fx1), max(y1, fy1)
                ix2, iy2 = min(x2, fx2), min(y2, fy2)
                inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
                union = (x2-x1)*(y2-y1) + (fx2-fx1)*(fy2-fy1) - inter
                iou   = inter / union if union > 0 else 0.0
                if iou > best_iou:
                    best_iou  = iou
                    best_face = face

            if best_face is not None and best_iou >= 0.3:
                results.append({
                                    "track_id": track_id,
                                    "bbox":     (x1, y1, x2, y2),
                                    "face":     best_face,
                                })
        return results