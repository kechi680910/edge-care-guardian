from __future__ import annotations

from collections import defaultdict

from .events import CareEvent, EventType, SensorFrame, Severity


class FallDetector:
    """Temporal confirmation for a fall.

    Stage I validates the pipeline with lightweight posture/velocity inputs.
    Stage II swaps the raw inputs for HailoRT model output while preserving this
    temporal confirmation and cooldown behavior, so the policy and privacy
    layers are unchanged.
    """

    def __init__(
        self,
        impact_velocity_mps: float = -1.3,
        lying_frames: int = 2,
        minimum_confidence: float = 0.8,
    ) -> None:
        self.impact_velocity_mps = impact_velocity_mps
        self.lying_frames = lying_frames
        self.minimum_confidence = minimum_confidence
        self._floor_counts: dict[str, int] = defaultdict(int)

    def evaluate(self, frame: SensorFrame) -> CareEvent | None:
        posture = str(frame.values.get("posture", "unknown"))
        velocity = float(frame.values.get("vertical_velocity_mps", 0.0))
        model_confidence = float(frame.values.get("posture_confidence", 0.0))
        impact = velocity <= self.impact_velocity_mps

        if posture in {"lying", "floor"} and model_confidence >= self.minimum_confidence:
            self._floor_counts[frame.resident_id] += 1
        else:
            self._floor_counts[frame.resident_id] = 0

        confirmed = self._floor_counts[frame.resident_id] >= self.lying_frames
        if not (confirmed and impact):
            return None

        confidence = min(0.99, 0.55 * model_confidence + 0.45 * min(abs(velocity) / 2.5, 1.0))
        return CareEvent(
            event_type=EventType.FALL,
            severity=Severity.CRITICAL,
            confidence=round(confidence, 3),
            zone=frame.zone,
            resident_id=frame.resident_id,
            evidence={
                "posture": posture,
                "vertical_velocity_mps": velocity,
                "confirmed_frames": self._floor_counts[frame.resident_id],
            },
            timestamp=frame.timestamp,
        )


class WanderingDetector:
    """Restricted-zone presence, e.g. a dementia resident in a no-go zone."""

    def __init__(self, minimum_confidence: float = 0.75) -> None:
        self.minimum_confidence = minimum_confidence

    def evaluate(self, frame: SensorFrame) -> CareEvent | None:
        if not bool(frame.values.get("restricted_exit", False)):
            return None
        confidence = float(frame.values.get("presence_confidence", 0.9))
        if confidence < self.minimum_confidence:
            return None
        return CareEvent(
            event_type=EventType.WANDERING,
            severity=Severity.HIGH,
            confidence=confidence,
            zone=frame.zone,
            resident_id=frame.resident_id,
            evidence={"restricted_exit": True, "presence_confidence": confidence},
            timestamp=frame.timestamp,
        )


class MedicationDetector:
    """Smart-box signal: a scheduled dose left untaken past a grace window."""

    def __init__(
        self,
        medium_minutes: int = 15,
        high_minutes: int = 60,
    ) -> None:
        self.medium_minutes = medium_minutes
        self.high_minutes = high_minutes

    def evaluate(self, frame: SensorFrame) -> CareEvent | None:
        minutes_late = int(frame.values.get("medication_minutes_late", 0))
        if minutes_late < self.medium_minutes:
            return None
        severity = Severity.HIGH if minutes_late >= self.high_minutes else Severity.MEDIUM
        return CareEvent(
            event_type=EventType.MEDICATION_MISSED,
            severity=severity,
            confidence=1.0,
            zone=frame.zone,
            resident_id=frame.resident_id,
            evidence={"minutes_late": minutes_late},
            timestamp=frame.timestamp,
        )


class DistressDetector:
    """Wake-word / vocal-cue distress, processed entirely on-device.

    The microphone runs local wake-word / cue detection only; the raw audio
    never leaves the room. A single strong cue is treated as MEDIUM; a
    repeated cue within the confirmation window escalates to HIGH. This keeps
    the distress path consistent with the "temporal confirmation before alert"
    design principle in the deck.
    """

    def __init__(
        self,
        confirmation_cues: int = 2,
        cue_window_seconds: float = 20.0,
    ) -> None:
        self.confirmation_cues = confirmation_cues
        self.cue_window = cue_window_seconds
        self._cue_counts: dict[str, int] = {}
        self._last_cue: dict[str, datetime] = {}

    def evaluate(self, frame: SensorFrame) -> CareEvent | None:
        cue = bool(frame.values.get("distress_cue", False))
        if not cue:
            self._cue_counts[frame.resident_id] = 0
            return None

        now = frame.timestamp
        last = self._last_cue.get(frame.resident_id)
        if last is not None and (now - last).total_seconds() <= self.cue_window:
            self._cue_counts[frame.resident_id] = self._cue_counts.get(frame.resident_id, 0) + 1
        else:
            self._cue_counts[frame.resident_id] = 1
        self._last_cue[frame.resident_id] = now

        count = self._cue_counts[frame.resident_id]
        severity = Severity.HIGH if count >= self.confirmation_cues else Severity.MEDIUM
        confidence = float(frame.values.get("cue_confidence", 0.9))
        return CareEvent(
            event_type=EventType.DISTRESS,
            severity=severity,
            confidence=confidence,
            zone=frame.zone,
            resident_id=frame.resident_id,
            evidence={"cues_in_window": count, "cue_confidence": confidence},
            timestamp=now,
        )
