"""Append-only audit trail of agent runs (JSON Lines)."""

import hashlib
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_RESERVED_KEYS = ("timestamp", "event_id")


def sha256_file(path: Path) -> str:
    """Return the hex SHA-256 digest of the file at `path`."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def append_audit_event(path: Path, event: dict[str, Any]) -> None:
    """Append `event` as one JSON line to `path`, stamped with a UTC timestamp and event_id.

    The file is only ever opened in append mode, so earlier events are never
    rewritten. Each write is flushed and synced to disk before returning.
    """
    clash = [key for key in _RESERVED_KEYS if key in event]
    if clash:
        raise ValueError(f"audit event must not set {clash}; they are added automatically")
    record = {
        "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "event_id": str(uuid.uuid4()),
        **event,
    }
    line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as handle:
        handle.write(line.encode("utf-8"))
        handle.flush()
        os.fsync(handle.fileno())
