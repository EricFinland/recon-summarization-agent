"""Audit log tests: append-only JSON Lines with timestamps and event ids."""

import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest

from recon_agent.audit import append_audit_event, sha256_file


def _lines(path):
    return path.read_bytes().decode("utf-8").splitlines()


def test_two_events_make_two_lines_and_earlier_content_is_untouched(tmp_path):
    log = tmp_path / "logs" / "audit.log.jsonl"
    append_audit_event(log, {"step": "first", "note": "multi\nline"})
    first_bytes = log.read_bytes()
    append_audit_event(log, {"step": "second"})

    assert log.read_bytes().startswith(first_bytes)
    lines = _lines(log)
    assert len(lines) == 2
    first, second = (json.loads(line) for line in lines)
    assert (first["step"], first["note"], second["step"]) == ("first", "multi\nline", "second")
    assert first["event_id"] != second["event_id"]


def test_existing_log_content_is_preserved(tmp_path):
    log = tmp_path / "audit.log.jsonl"
    log.write_bytes(b'{"step": "older run"}\n')
    append_audit_event(log, {"step": "new"})
    assert _lines(log)[0] == '{"step": "older run"}'
    assert json.loads(_lines(log)[1])["step"] == "new"


def test_event_is_stamped_with_utc_timestamp(tmp_path):
    log = tmp_path / "audit.log.jsonl"
    append_audit_event(log, {"step": "x", "path": tmp_path})
    record = json.loads(_lines(log)[0])

    assert list(record)[:2] == ["timestamp", "event_id"]
    assert record["timestamp"].endswith("Z")
    stamp = datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))
    assert abs(datetime.now(UTC) - stamp) < timedelta(minutes=1)
    assert record["path"] == str(tmp_path)


def test_reserved_keys_are_rejected(tmp_path):
    with pytest.raises(ValueError, match="timestamp"):
        append_audit_event(tmp_path / "a.jsonl", {"timestamp": "yesterday"})
    assert not (tmp_path / "a.jsonl").exists()


def test_sha256_file(tmp_path):
    path = tmp_path / "f.bin"
    path.write_bytes(b"scan data" * 10000)
    assert sha256_file(path) == hashlib.sha256(b"scan data" * 10000).hexdigest()
