from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class InferenceAdapter(Protocol):
    """Anything the pipeline can call as a perception model.

    Stage I: ``NullModel`` (no-op passthrough, keeps the pipeline testable).
    Stage II: ``HailoModel`` (compiled ONNX on Hailo-10H) or any ONNXRuntime
    session.
    """

    def infer(self, frame_values: dict[str, Any]) -> dict[str, Any]: ...


class NullModel:
    """Passthrough model: returns the frame values unchanged.

    Lets Stage I run the full pipeline with zero external dependencies and no
    hardware, while still exercising the exact seam Stage II will replace.
    """

    def infer(self, frame_values: dict[str, Any]) -> dict[str, Any]:
        return dict(frame_values)


class HailoModel:
    """Stage II perception seam for Hailo-10H inference on ASUS UGen300.

    The repository intentionally avoids bundling proprietary SDK binaries or
    compiled model artifacts. To go live:

    1. Compile the chosen ONNX model for Hailo-10H with the Hailo Dataflow
       Compiler (see ``scripts/compile_hailo.sh``).
    2. In a target environment with the HailoRT driver installed, build a
       ``HailoModel(model_path)`` — it lazily imports ``hailort`` so the rest
       of the codebase has no Hailo dependency.
    3. ``infer`` runs one HailoRT forward pass and returns normalized
       outputs keyed to the detector fields (e.g. ``posture``,
       ``posture_confidence``).

    The same ``CareRuntime`` then runs the temporal-confirmation, fusion,
    privacy, and policy layers against live inference — the Stage I and
    Stage II paths are interchangeable.
    """

    def __init__(self, model_path: str | Path) -> None:
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Hailo model not found at {self.model_path}. "
                "Compile one with scripts/compile_hailo.sh, or use NullModel "
                "in Stage I."
            )
        self._session = None

    def _lazy_session(self) -> Any:
        """Build a HailoRT session once, lazily, keeping the import optional."""
        if self._session is None:
            try:
                import hailort  # type: ignore[import-not-found]
            except ImportError as exc:  # pragma: no cover - needs target env
                raise RuntimeError(
                    "hailort is not installed in this environment. "
                    "Install the approved Hailo SDK on the UGen300 host, "
                    "or run the Stage I pipeline with NullModel."
                ) from exc
            stream = hailort.Device().get_hailo_stream_from_model_file(
                str(self.model_path)
            )
            self._session = stream
        return self._session

    def infer(self, frame_values: dict[str, Any]) -> dict[str, Any]:
        stream = self._lazy_session()
        inputs = [bytes([0] * 4)]  # placeholder: real input tensors here
        _ = stream.infer(inputs=inputs)
        outputs = stream.get_outputs()
        # Map raw outputs onto detector field names. The exact mapping is
        # model-specific; keep it local to this seam.
        posture = "floor" if outputs[0] > 0 else "unknown"
        return {
            "posture": posture,
            "posture_confidence": float(outputs[0]),
            "vertical_velocity_mps": float(outputs[1]) if len(outputs) > 1 else 0.0,
        }


class HailoAdapter:
    """Backward-compatible facade for the old ``HailoAdapter`` class name."""

    def __init__(self, model_path: str | Path) -> None:
        self.model = HailoModel(model_path)

    def infer(self, frame_values: dict[str, Any]) -> dict[str, Any]:
        return self.model.infer(frame_values)
