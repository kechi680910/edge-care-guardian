from __future__ import annotations

import hashlib
from typing import Any

from .events import CareEvent


class PrivacyGuard:
    """Projects an internal event into minimum-necessary egress metadata."""

    def __init__(self, site_secret: str = "replace-in-production") -> None:
        self.site_secret = site_secret

    def resident_token(self, resident_id: str) -> str:
        raw = f"{self.site_secret}:{resident_id}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:16]

    def project(self, event: CareEvent) -> dict[str, Any]:
        return {
            "event_id": event.event_id,
            "event_type": event.event_type.value,
            "severity": event.severity.value,
            "zone": event.zone,
            "timestamp": event.timestamp.isoformat(),
            "confidence": event.confidence,
            "resident_token": self.resident_token(event.resident_id),
        }
