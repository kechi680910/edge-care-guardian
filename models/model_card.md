# Model Card — Stage II Edge Perception Stack

## Intended use

Local perception for care-assistance events: posture/fall sequence, restricted-zone presence, activity context, and vocal distress cues. Outputs are signals for a deterministic policy and human escalation; they are not diagnoses.

## Candidate model pipeline

1. Person detection or pose estimation from the Hailo Model Zoo / an ONNX-compatible model with a license suitable for competition use.
2. Quantization and compilation with the Hailo Dataflow Compiler for Hailo-10H.
3. HailoRT execution through `HailoModel` (`hailo_adapter.py`).
4. Temporal confirmation in `FallDetector` / `DistressDetector` to avoid treating one frame as an event.
5. Stage I runs the identical pipeline with `NullModel` (passthrough) so the policy and privacy layers are validated without hardware.

## Required validation

- Subject-disjoint train/validation/test sets.
- Older-adult and mobility-aid scenarios represented.
- Public-space RGB tests separated from privacy-zone radar/thermal tests.
- Report recall, precision, false alerts per room-day, end-to-end latency, and performance by lighting/occlusion condition.
- Conduct a site pilot with caregivers; do not infer clinical efficacy from benchmark accuracy alone.

## Known limitations

- Simulation inputs in Stage I are not measured hardware performance.
- Posture alone is insufficient; temporal motion and context are required.
- Blankets, occlusion, wheelchairs, pets, and caregiver assistance can create hard negatives.
- Camera-based models are inappropriate for some private zones without explicit consent and privacy transformation.

## Safety

Critical alerts require human verification. The system must fail safe during network loss and expose a physical disable/control mechanism.
