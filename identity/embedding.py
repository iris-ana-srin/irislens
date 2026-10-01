#embedding.py
import numpy as np

class EmbeddingSmoother:
    def __init__(self, window: int = 5):
        self.window = window
        self._history: dict[int, list] = {}

    def update(self, track_id: int, embedding: np.ndarray) -> np.ndarray:
        buf = self._history.setdefault(track_id, [])
        buf.append(embedding.astype("float32"))
        if len(buf) > self.window:
            buf.pop(0)
        return np.mean(buf, axis=0)

    def reset(self, track_id: int | None = None):
        if track_id is None:
            self._history.clear()
        else:
            self._history.pop(track_id, None)