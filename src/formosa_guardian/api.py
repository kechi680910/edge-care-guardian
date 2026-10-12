from __future__ import annotations

from datetime import datetime
from typing import Any

try:
    from fastapi import FastAPI
    from pydantic import BaseModel
except ImportError as exc:  # pragma: no cover - optional dependency
    raise RuntimeError("Install with: pip install -e '.[api]'") from exc

from .events import SensorFrame
from .pipeline import OfflineQueue
from .runtime import CareRuntime

app = FastAPI(title="Formosa Care Guardian", version="0.2.0")

# A shared queue means the API and the local router agree on what is pending.
runtime = CareRuntime(queue=OfflineQueue())


class FrameRequest(BaseModel):
    resident_id: str
    zone: str
    values: dict[str, Any]
    timestamp: datetime | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "local-edge", "pending_egress": str(len(runtime.queue))}


@app.post("/frames")
def frames(request: FrameRequest) -> list[dict[str, Any]]:
    kwargs: dict[str, Any] = {}
    if request.timestamp is not None:
        kwargs["timestamp"] = request.timestamp
    frame = SensorFrame(
        resident_id=request.resident_id,
        zone=request.zone,
        values=request.values,
        **kwargs,
    )
    return runtime.process(frame)
