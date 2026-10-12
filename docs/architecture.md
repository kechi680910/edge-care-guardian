# Architecture and Stage II Integration

## Deployment unit

- **Host:** compact x86/SBC host supported by the competition environment.
- **Accelerator:** ASUS UGen300 (M.2 or USB), Hailo-10H, 8 GB dedicated memory, 40 TOPS INT4 / 20 TOPS INT8, 2.5 W typical.
- **Sensors:** RGB/IR camera in consented public zones; mmWave/thermal/bed sensors in private zones; smart medication box and optional microphone with local wake-word / cue detection.
- **Outputs:** local speaker/light, caregiver application, nurse station, and encrypted local event log.

## Data flow and trust boundaries

1. Sensor adapters normalize timestamps and zone identifiers.
2. Raw data enters a volatile local preprocessing buffer.
3. The perception model runs locally; raw media is discarded by default.
4. Temporal fusion confirms the event and suppresses duplicates.
5. Privacy Guard pseudonymizes the resident identity and enforces an egress allowlist.
6. Escalation Policy sends minimum-necessary metadata to human caregivers.
7. During an outage, actions continue locally and events queue for approved synchronization; an encrypted local audit log seals every event.

## Care moments

| Moment | Detector | Typical trigger | Severity model |
|---|---|---|---|
| Fall | `FallDetector` | Two confirmed floor frames + impact velocity | CRITICAL |
| Wandering | `WanderingDetector` | Restricted-zone presence above a confidence floor | HIGH |
| Medication | `MedicationDetector` | Dose left untaken past the grace window | MEDIUM → HIGH |
| Distress | `DistressDetector` | On-device wake-word / cue; repeated cue within window | MEDIUM → HIGH |

The same `CareRuntime` loop (detect → fuse → privacy → policy → queue/log) runs every moment, so the system is one pipeline, not four products.

## Stage II work packages

### WP1 — Perception on UGen300

- Select and license the model (Hailo Model Zoo / a competition-approved ONNX model).
- Export ONNX; calibrate with representative care-environment data.
- Compile with Hailo Dataflow Compiler; execute with HailoRT through `HailoModel`.
- Measure latency, throughput, temperature, and memory.

### WP2 — Sensor fusion and false-alert control

- Add mmWave/bed-sensor adapters.
- Tune temporal windows and zone-specific policies.
- Build a hard-negative scenario set: sitting quickly, kneeling, picking up objects, assisted transfers, pets, and occlusion.

### WP3 — Care workflow

- Implement acknowledge/escalate/resolve states on top of `OfflineQueue`.
- Add caregiver roster, offline sync, and audit export from `EncryptedEventLog`.
- Run tabletop drills with caregivers and document human factors.

### WP4 — Privacy and security

- Consent and role-based access.
- Egress allowlist and packet-capture verification (`FORBIDDEN_EGRESS_FIELDS` in `pipeline.py` is the testable guard).
- Encryption at rest; signed model/config updates.
- Threat model and incident-response checklist.

## Non-goals

The prototype does not diagnose, prescribe, autonomously contact emergency services, or replace a caregiver. Robotics mobility and drone functions from earlier concepts are intentionally excluded from the Stage I core to maximize feasibility on the Battlefield Lightning platform.
