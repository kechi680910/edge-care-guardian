"""Formosa Care Guardian edge-event pipeline.

A privacy-first, offline-capable care-assistance system. Stage I runs the
full loop with zero external dependencies; Stage II swaps in HailoRT-backed
perception through the same seams.
"""

from .events import (
    CareEvent,
    EscalationAction,
    EventType,
    QueuedEvent,
    SensorFrame,
    Severity,
)
from .hailo_adapter import HailoAdapter, HailoModel, InferenceAdapter, NullModel
from .pipeline import EncryptedEventLog, OfflineQueue
from .runtime import CareRuntime

__all__ = [
    "CareEvent",
    "CareRuntime",
    "EncryptedEventLog",
    "EscalationAction",
    "EventType",
    "HailoAdapter",
    "HailoModel",
    "InferenceAdapter",
    "NullModel",
    "OfflineQueue",
    "QueuedEvent",
    "SensorFrame",
    "Severity",
]
__version__ = "0.2.0"
