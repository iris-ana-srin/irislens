#decisionengine.py
from dataclasses import dataclass
from config import SIM_THRESHOLD

@dataclass
class Decision:
    status:     str            # "KNOWN" | "UNKNOWN" | "SPOOF" | "NO_FACE"
    username:   str | None
    password:   str | None
    confidence: float
    label:      str
    color:      tuple


class DecisionEngine:
    def __init__(self, sim_threshold: float = SIM_THRESHOLD):
        self.sim_threshold = sim_threshold

    def evaluate(
                    self,
                    score:          float | None,
                    username:       str   | None,
                    password:       str   | None,
                    voted_username: str   | None,
                ) -> Decision:
        if score is None:
            return Decision("UNKNOWN", None, None, 0.0, "UNKNOWN", (0, 0, 255))

        resolved_username = voted_username if voted_username else username
        if score >= self.sim_threshold:
            label = f"{resolved_username} ({score:.2f})"
            return Decision(
                "KNOWN", resolved_username, password, score, label, (0, 255, 0))

        label = f"UNKNOWN ({score:.2f})"
        return Decision("UNKNOWN", None, None, score, label, (0, 0, 255))