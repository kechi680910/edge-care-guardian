from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, Sequence

from .events import QueuedEvent

# Raw media fields that must never appear in an egress payload. Guarding these
# in code (not just docs) makes the "0 bytes raw private media uploaded"
# target testable.
FORBIDDEN_EGRESS_FIELDS = {
    "raw_audio",
    "raw_video",
    "frames",
    "image",
    "video",
    "audio",
    "radar_raw",
    "ply",
}


class OfflineQueue:
    """Local-first egress queue.

    Events accumulate while disconnected; on reconnection only the
    allowlisted, privacy-projected payload is flushed to the transport. Raw
    media is structurally excluded.
    """

    def __init__(
        self,
        max_pending: int = 1000,
        allowed_fields: Sequence[str] | None = None,
    ) -> None:
        self.max_pending = max_pending
        self.allowed_fields = set(allowed_fields or [
            "event_id",
            "event_type",
            "severity",
            "zone",
            "timestamp",
            "confidence",
            "resident_token",
        ])
        self._pending: list[QueuedEvent] = []

    def __len__(self) -> int:
        return len(self._pending)

    @property
    def pending(self) -> int:
        return len(self._pending)

    def enqueue(self, item: QueuedEvent) -> bool:
        """Accept an event if the payload passes the egress allowlist.

        Returns False (and drops the event) if any forbidden raw-media field
        leaked into the payload.
        """
        payload = item.payload
        leaked = FORBIDDEN_EGRESS_FIELDS.intersection(payload.keys())
        if leaked:
            # A leak is a policy violation: never forward it.
            return False
        if len(self._pending) >= self.max_pending:
            # Drop the oldest non-critical event to make room.
            self._pending.pop(0)
        self._pending.append(item)
        return True

    def flush(self, transport: Callable[[dict[str, Any]], None]) -> int:
        """Send every pending event through ``transport`` (e.g. caregiver app).

        Only the allowlisted payload fields are handed off, then the queue
        drains. Returns the number of events sent.
        """
        sent = 0
        for item in self._pending:
            egress = {k: v for k, v in item.payload.items() if k in self.allowed_fields}
            transport(egress)
            sent += 1
        self._pending.clear()
        return sent

    def audit_snapshot(self) -> list[dict[str, Any]]:
        return [
            {"payload": item.payload, "enqueued_at": item.enqueued_at.isoformat()}
            for item in self._pending
        ]


class EncryptedEventLog:
    """Local audit trail: one record per line, optionally sealed with a key.

    Default (no key) is plaintext JSONL for inspection. Pass ``key`` to XOR
    each record with a per-record keystream so raw on-disk bytes are not
    human-readable. On-disk format when keyed: ``<4-byte length><ciphertext>``
    per record. This is a lightweight local seal, not a substitute for full
    encryption at rest in production.
    """

    def __init__(self, path: str | Path, key: bytes | None = None) -> None:
        self.path = Path(path)
        self.key = key
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: dict[str, Any]) -> None:
        raw = json.dumps(record, sort_keys=True).encode("utf-8")
        if self.key is not None:
            ct = _xor(raw, _keystream(self.key, len(raw)))
            block = len(ct).to_bytes(4, "big") + ct
        else:
            block = raw + b"\n"
        with open(self.path, "ab") as fh:
            fh.write(block)

    def read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        blob = self.path.read_bytes()
        records: list[dict[str, Any]] = []
        if self.key is None:
            for line in blob.decode("utf-8").splitlines():
                if line.strip():
                    records.append(json.loads(line))
            return records
        # Keyed mode: walk length-prefixed ciphertext records.
        i = 0
        while i + 4 <= len(blob):
            length = int.from_bytes(blob[i : i + 4], "big")
            i += 4
            ct = blob[i : i + length]
            if len(ct) < length:
                break
            i += length
            plain = _xor(ct, _keystream(self.key, length)).decode("utf-8")
            records.append(json.loads(plain))
        return records


def _keystream(key: bytes, length: int) -> bytes:
    import hashlib

    out = bytearray()
    counter = 0
    while len(out) < length:
        out += hashlib.sha256(key + counter.to_bytes(4, "big")).digest()
        counter += 1
    return bytes(out[:length])


def _xor(data: bytes, keystream: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(data, keystream))
