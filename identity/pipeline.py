#face_pipeline.py
from __future__ import annotations
from dataclasses import dataclass, field
from identity.framefilter    import FrameQualityFilter
from identity.detector       import FaceDetector
from identity.tracker        import FaceTracker
from identity.liveness       import LivenessChecker
from identity.embedding      import EmbeddingSmoother
from identity.database       import FaceDatabase
from identity.temporalvoter  import TemporalVoter
from identity.decisionengine import DecisionEngine, Decision
from identity.auditlogger    import AuditLogger

@dataclass
class FrameResult:
    frame_rejected: bool = False
    frame_reason:   str  = ""
    tracks: list[TrackResult] = field(default_factory=list)

@dataclass
class TrackResult:
    track_id:    int
    bbox:        tuple
    decision:    Decision
    liveness_ok: bool

class MPipeline:
    """One Pipeline per camera. 
    Tracking/voting/smoothing state(tracker, voter, smoother) per-camera.
    Detector, database, audit logger are shared across cameras.
    """
    def __init__(self, db: FaceDatabase, gpu: bool = True, camera_id: str | None = None,
                 detector: FaceDetector | None = None, audit: AuditLogger | None = None):
        self.camera_id     = camera_id
        self.frame_filter  = FrameQualityFilter()
        self.detector      = detector or FaceDetector(gpu=gpu)
        self.tracker        = FaceTracker()
        self.liveness       = LivenessChecker()
        self.smoother        = EmbeddingSmoother()
        self.db               = db
        self.voter             = TemporalVoter()
        self.decision           = DecisionEngine()
        self.audit               = audit or AuditLogger()

        print(f"[FacePipeline:{camera_id}] All stages initialised.")

    def process_frame(self, frame) -> FrameResult:
        result = FrameResult()

        passed, reason = self.frame_filter.check(frame)
        if not passed:
            result.frame_rejected = True
            result.frame_reason   = reason
            return result

        faces = self.detector.detect(frame)
        if not faces:
            return result

        tracked = self.tracker.update(faces)
        for t in tracked:
            track_id = t["track_id"]
            bbox     = t["bbox"]
            face     = t["face"]

            live = self.liveness.check(frame, bbox)
            if not live:
                spoof_decision = Decision(status="SPOOF", username=None, password=None, confidence=0.0, label="Spoof detected", color=(0, 0, 255),)
                result.tracks.append(TrackResult(track_id, bbox, spoof_decision, False))
                continue

            smooth_emb = self.smoother.update(track_id, face.embedding)

            score, username, password = self.db.search(smooth_emb)
            if username:
                self.voter.update(track_id, username)

            #bypass voter for very high confidence matches
            FAST_PATH_THRESHOLD = 0.88  #tobetuned
            if score is not None and score >= FAST_PATH_THRESHOLD:
                voted_username = username
            else:
                voted_username = self.voter.vote(track_id)

            dec = self.decision.evaluate(score, username, password, voted_username)
            result.tracks.append(TrackResult(track_id, bbox, dec, True))

        return result

    def log_session_result(self, *, status: str, username, confidence: float):
        self.audit.log(
                            status=status, username=username, confidence=confidence,
                            extra={"camera_id": self.camera_id} if self.camera_id else None,
                        )