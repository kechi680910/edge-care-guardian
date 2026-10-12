from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .events import SensorFrame
from .pipeline import EncryptedEventLog, OfflineQueue
from .runtime import CareRuntime


def _emit(result: dict) -> None:
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> None:
    # Shared local loop: offline queue + encrypted audit log, one runtime.
    queue = OfflineQueue()
    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "audit.jsonl"
        event_log = EncryptedEventLog(log_path, key=b"demo-site-key")
        runtime = CareRuntime(queue=queue, event_log=event_log)
        t0 = datetime.now(timezone.utc)

        frames: list[SensorFrame] = [
            # Normal activity: no alert.
            SensorFrame(
                "resident-001", "bedroom",
                {"posture": "standing", "posture_confidence": 0.97},
                t0,
            ),
            # Simulated fall sequence (two confirmed floor frames + impact).
            SensorFrame(
                "resident-001", "bedroom",
                {"posture": "floor", "posture_confidence": 0.94,
                 "vertical_velocity_mps": -1.8},
                t0 + timedelta(milliseconds=120),
            ),
            SensorFrame(
                "resident-001", "bedroom",
                {"posture": "floor", "posture_confidence": 0.96,
                 "vertical_velocity_mps": -1.7},
                t0 + timedelta(milliseconds=240),
            ),
            # Wandering into a restricted zone.
            SensorFrame(
                "resident-001", "kitchen",
                {"restricted_exit": True, "presence_confidence": 0.92},
                t0 + timedelta(seconds=3),
            ),
            # Missed medication past the HIGH threshold.
            SensorFrame(
                "resident-001", "kitchen",
                {"medication_minutes_late": 90},
                t0 + timedelta(seconds=4),
            ),
            # Distress: first cue is MEDIUM, second escalates to HIGH.
            SensorFrame(
                "resident-001", "bedroom",
                {"distress_cue": True, "cue_confidence": 0.9},
                t0 + timedelta(seconds=6),
            ),
            SensorFrame(
                "resident-001", "bedroom",
                {"distress_cue": True, "cue_confidence": 0.93},
                t0 + timedelta(seconds=8),
            ),
        ]

        print("# Formosa Care Guardian — local care-event demo")
        print("# Four care moments run through one offline-first loop.\n")
        for frame in frames:
            for result in runtime.process(frame):
                _emit(result)

        # Network outage simulation: flush the queue to a stand-in transport.
        delivered: list[dict] = []

        def transport(payload: dict) -> None:
            delivered.append(payload)

        print("\n# Caregiver app reconnects -> flush pending egress queue")
        sent = queue.flush(transport)
        print(f"# Sent {sent} privacy-projected event(s); "
              f"raw media fields forwarded: {sum('raw_audio' in p for p in delivered)}\n")
        for p in delivered:
            print(f"  egress -> {json.dumps(p, ensure_ascii=False)}")

        # Sealed audit trail: decrypt and re-read.
        records = event_log.read()
        print(f"\n# Encrypted local audit log held {len(records)} sealed record(s).")

        # Persist a stable receipt (privacy-projected only) for the repo.
        receipt = {
            "generated": datetime.now(timezone.utc).isoformat(),
            "pending_flushed": sent,
            "egress_samples": delivered,
            "audit_records": [
                {"event": r["event"], "actions": r["actions"]} for r in records
            ],
        }
        out = Path(__file__).with_name("demo-receipt.json")
        out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n# Wrote {out.name} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
