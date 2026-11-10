"""Output writer tests: file name, format, and atomic replacement."""

import json
import os
from datetime import UTC, datetime

import pytest

from recon_agent import output
from recon_agent.models import ScanHost, ScanResult
from recon_agent.summarizer import summarize


@pytest.fixture
def summary():
    scan = ScanResult(scan_id="s-1", hosts=[ScanHost(ip="10.0.0.1", notes=["Titel: Größe"])])
    return summarize(scan, "scan.json", generated_at=datetime(2026, 11, 1, tzinfo=UTC))


def test_writes_pretty_utf8_json_named_after_input_stem(tmp_path, summary):
    out_dir = tmp_path / "nested" / "out"
    path = output.write_output(summary, out_dir, "dir/sample_scan_03.xml")

    assert path == out_dir / "sample_scan_03.summary.json"
    text = path.read_bytes().decode("utf-8")
    assert text.endswith("}\n")
    assert "\r\n" not in text
    assert text.splitlines()[1].startswith('  "schema_version"')
    assert "Größe" in text
    assert json.loads(text) == summary.model_dump(mode="json")
    assert json.loads(text)["generated_at"] == "2026-11-01T00:00:00Z"


def test_overwrites_and_leaves_no_temp_files(tmp_path, summary):
    output.write_output(summary, tmp_path, "scan.json")
    summary.overview.summary_text = "second"
    path = output.write_output(summary, tmp_path, "scan.json")

    assert json.loads(path.read_text(encoding="utf-8"))["overview"]["summary_text"] == "second"
    assert [p.name for p in tmp_path.iterdir()] == ["scan.summary.json"]


def test_failed_replace_keeps_previous_file(tmp_path, summary, monkeypatch):
    path = output.write_output(summary, tmp_path, "scan.json")
    before = path.read_bytes()

    def broken_replace(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", broken_replace)
    summary.overview.summary_text = "never written"
    with pytest.raises(OSError, match="disk full"):
        output.write_output(summary, tmp_path, "scan.json")

    assert path.read_bytes() == before
    assert [p.name for p in tmp_path.iterdir()] == ["scan.summary.json"]
