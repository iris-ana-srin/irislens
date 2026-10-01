#temporalvoter.py
from collections import Counter

class TemporalVoter:
    def __init__(self, window: int = 5, min_votes: int = 3):
        self.window    = window
        self.min_votes = min_votes
        self._history: dict[int, list[str]] = {}

    def update(self, track_id: int, username: str):
        buf = self._history.setdefault(track_id, [])
        buf.append(username)
        if len(buf) > self.window:
            buf.pop(0)

    def vote(self, track_id: int) -> str | None:
        buf = self._history.get(track_id, [])
        if not buf:
            return None
        best_id, count = Counter(buf).most_common(1)[0]
        return best_id if count >= self.min_votes else None

    def reset(self, track_id: int | None = None):
        if track_id is None:
            self._history.clear()
        else:
            self._history.pop(track_id, None)