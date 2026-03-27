"""Lightweight append-only audit trail for subject context writes."""

from datetime import UTC, datetime
import json

from hda.config import get_active_subject, get_context_path


AUDIT_FILENAME = ".audit_log.jsonl"


def get_context_audit_path(subject: str | None = None):
    subject = subject or get_active_subject()
    return get_context_path(subject) / AUDIT_FILENAME


def append_context_audit(
    event_type: str,
    subject: str | None = None,
    section: str | None = None,
    details: dict | None = None,
) -> dict:
    """Append one audit event for a subject context mutation."""
    subject = subject or get_active_subject()
    path = get_context_audit_path(subject)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "subject": subject,
        "event_type": event_type,
        "section": section,
        "details": details or {},
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=True) + "\n")
    return entry


def read_context_audit(subject: str | None = None, limit: int = 50) -> dict:
    """Read recent audit events for a subject context folder."""
    subject = subject or get_active_subject()
    path = get_context_audit_path(subject)
    if not path.exists():
        return {"subject": subject, "path": str(path), "entries": []}

    entries = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            entries.append(json.loads(line))
    return {"subject": subject, "path": str(path), "entries": entries[-limit:]}
