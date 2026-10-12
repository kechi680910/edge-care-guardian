from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class EventType(str, Enum):
    FALL = "fall"
    WANDERING = "wandering"
    MEDICATION_MISSED = "medication_missed"
    DISTRESS = "distress"


class Severity(str, Enum):
    INFO = "info"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class SensorFrame:
    resident_id: str
    zone: str
    values: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class CareEvent:
    event_type: EventType
    severity: Severity
    confidence: float
    zone: str
    resident_id: str
    evidence: dict[str, Any]
    timestamp: datetime
    event_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True)
class EscalationAction:
    channel: str
    priority: int
    message: str
    requires_ack: bool


@dataclass(frozen=True)
class QueuedEvent:
    """An event projected for egress plus the audited actions attached to it.

    Stored locally by the offline queue; only the privacy-projected payload
    leaves the room, never raw media.
    """

    payload: dict[str, Any]
    actions: list[dict[str, Any]]
    local_audit: dict[str, Any]
    enqueued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
