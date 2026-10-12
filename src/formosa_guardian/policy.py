from __future__ import annotations

from .events import CareEvent, EscalationAction, Severity


class EscalationPolicy:
    """Human-in-the-loop routing; no clinical diagnosis is produced."""

    def actions_for(self, event: CareEvent) -> list[EscalationAction]:
        base = f"{event.event_type.value.replace('_', ' ').title()} detected in {event.zone}"
        actions = [
            EscalationAction(
                channel="local_voice",
                priority=1,
                message=f"{base}. Are you okay?",
                requires_ack=False,
            )
        ]
        if event.severity in {Severity.HIGH, Severity.CRITICAL}:
            actions.append(
                EscalationAction(
                    channel="caregiver_app",
                    priority=2,
                    message=base,
                    requires_ack=True,
                )
            )
        if event.severity is Severity.CRITICAL:
            actions.append(
                EscalationAction(
                    channel="nurse_station",
                    priority=3,
                    message=f"Critical: {base}; verify resident status immediately.",
                    requires_ack=True,
                )
            )
        return actions
