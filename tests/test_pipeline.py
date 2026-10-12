from datetime import datetime, timedelta, timezone
import tempfile
import unittest

from formosa_guardian.detectors import DistressDetector
from formosa_guardian.events import EventType, SensorFrame, Severity
from formosa_guardian.hailo_adapter import NullModel
from formosa_guardian.pipeline import EncryptedEventLog, OfflineQueue
from formosa_guardian.runtime import CareRuntime


class CarePipelineTests(unittest.TestCase):
    def test_confirmed_fall_emits_private_event_and_three_actions(self) -> None:
        runtime = CareRuntime()
        now = datetime.now(timezone.utc)
        first = SensorFrame(
            "resident-a",
            "bathroom",
            {
                "posture": "floor",
                "posture_confidence": 0.95,
                "vertical_velocity_mps": -1.8,
            },
            now,
        )
        second = SensorFrame(
            "resident-a",
            "bathroom",
            {
                "posture": "floor",
                "posture_confidence": 0.97,
                "vertical_velocity_mps": -1.7,
            },
            now + timedelta(milliseconds=100),
        )
        self.assertEqual(runtime.process(first), [])
        result = runtime.process(second)
        self.assertEqual(len(result), 1)
        event = result[0]["event"]
        self.assertEqual(event["event_type"], "fall")
        self.assertEqual(event["severity"], "critical")
        self.assertNotIn("resident_id", event)
        self.assertIn("resident_token", event)
        self.assertEqual(len(result[0]["actions"]), 3)

    def test_normal_activity_does_not_alert(self) -> None:
        runtime = CareRuntime()
        frame = SensorFrame(
            "resident-b",
            "living_room",
            {"posture": "sitting", "posture_confidence": 0.99},
        )
        self.assertEqual(runtime.process(frame), [])

    def test_medication_event_has_no_raw_sensor_payload(self) -> None:
        runtime = CareRuntime()
        frame = SensorFrame(
            "resident-c",
            "kitchen",
            {"medication_minutes_late": 30, "raw_audio": "never-egress"},
        )
        result = runtime.process(frame)
        self.assertEqual(result[0]["event"]["event_type"], "medication_missed")
        self.assertNotIn("raw_audio", result[0]["event"])

    # ---- new coverage ----

    def test_wandering_emits_high_event(self) -> None:
        runtime = CareRuntime()
        frame = SensorFrame(
            "resident-w", "kitchen",
            {"restricted_exit": True, "presence_confidence": 0.9},
        )
        result = runtime.process(frame)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["event"]["event_type"], "wandering")
        self.assertEqual(result[0]["event"]["severity"], "high")

    def test_distress_first_cue_is_medium(self) -> None:
        detector = DistressDetector()
        frame = SensorFrame(
            "resident-d", "bedroom",
            {"distress_cue": True, "cue_confidence": 0.9},
            datetime.now(timezone.utc),
        )
        event = detector.evaluate(frame)
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, EventType.DISTRESS)
        self.assertEqual(event.severity, Severity.MEDIUM)
        self.assertEqual(event.evidence["cues_in_window"], 1)

    def test_distress_repeated_cue_escalates_to_high(self) -> None:
        detector = DistressDetector()
        now = datetime.now(timezone.utc)
        detector.evaluate(SensorFrame(
            "resident-d", "bedroom",
            {"distress_cue": True, "cue_confidence": 0.9}, now,
        ))
        second = detector.evaluate(SensorFrame(
            "resident-d", "bedroom",
            {"distress_cue": True, "cue_confidence": 0.93},
            now + timedelta(seconds=5),
        ))
        self.assertIsNotNone(second)
        self.assertEqual(second.severity, Severity.HIGH)
        self.assertEqual(second.evidence["cues_in_window"], 2)

    def test_distress_cue_window_resets_after_gap(self) -> None:
        detector = DistressDetector(cue_window_seconds=20.0)
        now = datetime.now(timezone.utc)
        detector.evaluate(SensorFrame(
            "resident-d", "bedroom",
            {"distress_cue": True}, now,
        ))
        # 25s later > 20s window -> count restarts at 1.
        late = detector.evaluate(SensorFrame(
            "resident-d", "bedroom",
            {"distress_cue": True}, now + timedelta(seconds=25),
        ))
        self.assertIsNotNone(late)
        self.assertEqual(late.severity, Severity.MEDIUM)
        self.assertEqual(late.evidence["cues_in_window"], 1)

    def test_offline_queue_drops_raw_media_and_flushes_only_allowlist(self) -> None:
        queue = OfflineQueue()
        runtime = CareRuntime(queue=queue)
        now = datetime.now(timezone.utc)
        runtime.process(SensorFrame(
            "resident-q", "kitchen",
            {"medication_minutes_late": 90}, now,
        ))
        self.assertEqual(queue.pending, 1)
        delivered: list[dict] = []
        sent = queue.flush(delivered.append)
        self.assertEqual(sent, 1)
        self.assertEqual(queue.pending, 0)
        payload = delivered[0]
        for forbidden in ("raw_audio", "raw_video", "frames", "image", "video", "audio"):
            self.assertNotIn(forbidden, payload)
        self.assertIn("event_type", payload)
        self.assertIn("resident_token", payload)

    def test_offline_queue_rejects_leaked_raw_payload(self) -> None:
        from formosa_guardian.events import QueuedEvent
        queue = OfflineQueue()
        bad = QueuedEvent(
            payload={"event_type": "fall", "raw_audio": "must-not-leave"},
            actions=[],
            local_audit={},
        )
        self.assertFalse(queue.enqueue(bad))
        self.assertEqual(queue.pending, 0)

    def test_encrypted_event_log_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/audit.jsonl"
            log = EncryptedEventLog(path, key=b"site-key")
            log.append({"event": {"event_type": "fall"}, "seq": 1})
            log.append({"event": {"event_type": "distress"}, "seq": 2})
            # On-disk bytes must NOT contain the plaintext marker.
            raw = open(path, "rb").read()
            self.assertNotIn(b"distress", raw)
            self.assertEqual(len(log.read()), 2)
            self.assertEqual(log.read()[0]["seq"], 1)

    def test_hailo_seam_injects_model_and_keeps_pipeline(self) -> None:
        # A detector carrying a .model runs it first, then temporel logic.
        class HailoFallDetector:
            model = NullModel()

            def __init__(self) -> None:
                self.inner = None
                from formosa_guardian.detectors import FallDetector
                self.inner = FallDetector()

            def evaluate(self, frame):
                merged = frame.values | self.model.infer(frame.values)
                merged_frame = SensorFrame(
                    frame.resident_id, frame.zone, merged, frame.timestamp
                )
                return self.inner.evaluate(merged_frame)

        detector = HailoFallDetector()
        runtime = CareRuntime()
        runtime.detectors = [detector]  # replace default set with the Hailo path
        now = datetime.now(timezone.utc)
        runtime.process(SensorFrame(
            "resident-h", "bedroom",
            {"posture": "floor", "posture_confidence": 0.9,
             "vertical_velocity_mps": -1.8},
            now,
        ))
        out = runtime.process(SensorFrame(
            "resident-h", "bedroom",
            {"posture": "floor", "posture_confidence": 0.92,
             "vertical_velocity_mps": -1.6},
            now + timedelta(milliseconds=120),
        ))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["event"]["event_type"], "fall")
        # The merged model output (posture) should surface in evidence.
        self.assertEqual(out[0]["local_audit"]["evidence"]["posture"], "floor")


if __name__ == "__main__":
    unittest.main()
