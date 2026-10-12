# Security policy

Do not report resident data, credentials, model artifacts with restrictive licenses, or production site details in public issues. For a real deployment, use a private security contact, signed releases, encrypted local storage, role-based access, and an allowlisted outbound network policy. This competition prototype contains no real resident data.

## In-code controls

- `pipeline.py` enforces an egress allowlist; `FORBIDDEN_EGRESS_FIELDS` blocks raw media (audio, video, radar point clouds) from leaving the room.
- `privacy.py` pseudonymizes resident identity into a 16-hex `resident_token`.
- `EncryptedEventLog` seals the local audit trail with a site key; on-disk bytes are not human-readable.
- `HailoModel` does not bundle the Hailo SDK; the SDK is installed only on the target host.

## Production checklist

- Signed model and config updates.
- Outbound allowlist and packet-capture verification.
- Encrypted storage at rest; site-specific audit export.
- Consent, role-based access, and visible disable control.
- An incident-response runbook.
