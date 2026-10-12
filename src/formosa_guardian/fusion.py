from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .events import CareEvent


class EventFusion:
    """Suppresses duplicate events without hiding a new event class or zone."""

    def __init__(self, cooldown_seconds: int = 30) -> None:
        self.cooldown = timedelta(seconds=cooldown_seconds)
        self._last_seen: dict[tuple[str, str, str], datetime] = {}

    def accept(self, event: CareEvent) -> bool:
        key = (event.resident_id, event.zone, event.event_type.value)
        now = event.timestamp.astimezone(timezone.utc)
        previous = self._last_seen.get(key)
        if previous and now - previous < self.cooldown:
            return False
        self._last_seen[key] = now
        return True
