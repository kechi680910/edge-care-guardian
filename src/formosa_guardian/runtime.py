from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .detectors import (
    DistressDetector,
    FallDetector,
    MedicationDetector,
    WanderingDetector,
)
from .events import CareEvent, QueuedEvent, SensorFrame
from .fusion import EventFusion
from .pipeline import EncryptedEventLog, OfflineQueue, QueuedEvent as _Queued  # noqa: F401
from .policy import EscalationPolicy
from .privacy import PrivacyGuard


class CareRuntime:
    """Offline-first event pipeline shared by simulation and Hailo deployment.

    Wires all four care-moment detectors (fall, wandering, medication,
    distress) into the shared local loop: detect -> fuse -> privacy-project ->
    policy-route -> (queue / log). The same code runs against the simulated
    detectors in Stage I and against HailoRT-backed detectors in Stage II.
    """

    def __init__(
        self,
        queue: OfflineQueue | None = None,
        event_log: EncryptedEventLog | None = None,
    ) -> None:
        self.detectors = [
            FallDetector(),
            WanderingDetector(),
            MedicationDetector(),
            DistressDetector(),
        ]
        self.fusion = EventFusion(cooldown_seconds=30)
        self.privacy = PrivacyGuard()
        self.policy = EscalationPolicy()
        self.queue = queue if queue is not None else OfflineQueue()
        self.event_log = event_log

    def process(self, frame: SensorFrame) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for detector in self.detectors:
            event = self._detect(detector, frame)
            if event is None or not self.fusion.accept(event):
                continue

            projected = self.privacy.project(event)
            actions = [asdict(a) for a in self.policy.actions_for(event)]
            entry = {
                "event": projected,
                "actions": actions,
                "local_audit": {
                    "detector": detector.__class__.__name__,
                    "evidence": event.evidence,
                },
            }
            output.append(entry)

            # Persist to the offline queue so the alert survives a network
            # outage, then seal it into the local audit log.
            self.queue.enqueue(
                QueuedEvent(
                    payload=projected,
                    actions=actions,
                    local_audit=entry["local_audit"],
                    enqueued_at=event.timestamp,
                )
            )
            if self.event_log is not None:
                self.event_log.append(
                    {
                        "event": projected,
                        "actions": actions,
                        "local_audit": entry["local_audit"],
                    }
                )
        return output

    def _detect(self, detector: Any, frame: SensorFrame) -> CareEvent | None:
        """Run a detector; if it exposes a Hailo-injected model, feed frames.

        Stage II detectors set ``.model`` (an object with ``infer``). When
        present we run the model first and merge its output into the frame
        values, so the same temporal-confirmation logic is reused.
        """
        model = getattr(detector, "model", None)
        if model is None:
            return detector.evaluate(frame)
        model_out = model.infer(frame.values)
        merged = SensorFrame(
            resident_id=frame.resident_id,
            zone=frame.zone,
            values={**frame.values, **model_out},
            timestamp=frame.timestamp,
        )
        return detector.evaluate(merged)
