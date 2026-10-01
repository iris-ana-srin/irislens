#auditlogger.py
import json
import logging
import os
from datetime import datetime

from config import AUDIT_LOG_PATH

class AuditLogger:
    def __init__(self, log_path: str = AUDIT_LOG_PATH):
        os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
        self._logger = logging.getLogger("audit")
        self._logger.setLevel(logging.INFO)

        if not self._logger.handlers:
            handler = logging.FileHandler(log_path, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(handler)
        print(f"[AuditLogger] Writing to {log_path}")

    def log(self, *, status: str, username: str|None, confidence: float, extra: dict|None = None):
        record =    {
                        "timestamp":  datetime.now().isoformat(),
                        "status":     status,
                        "username":   username,
                        "confidence": round(confidence, 4),
                    }
        if extra:
            record.update(extra)
        self._logger.info(json.dumps(record))