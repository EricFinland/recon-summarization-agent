"""Pipeline tests: golden outputs, narrator fallback, and the audit trail. No network."""

import json
from pathlib import Path

import pytest

from recon_agent import pipeline
from recon_agent.loader import ScanLoadError
from recon_agent.pipeline import RunResult, SummaryValidationError, run, summarize_file
from tests.conftest import EXAMPLE_PAIRS, SCANS_DIR

GOOD_TEXT = "Five hosts were listed in 10.10.20.0/24, four of them up; SSH is open on port 22."


def _audit_events(settings) -> list[dict]:
    lines = settings.audit_log_path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def _comparable(doc: dict) -> dict:
    doc = json.loads(json.dumps(doc))
    doc.pop("generated_at")
    doc["overview"].pop("summary_text")
    return doc


@pytest.mark.parametrize("example,scan_path", EXAMPLE_PAIRS, ids=[e.name for e, _ in EXAMPLE_PAIRS])
def test_golden_examples(example: Path, scan_path: Path | None, tmp_settings):
    assert scan_path is not None, f"no unique data/scans file for {example.name}"
    result = run(scan_path, settings=tmp_settings)

    assert result.output_path == tmp_settings.output_dir / example.name
    actual = json.loads(result.output_path.read_text(encoding="utf-8"))
    expected = json.loads(example.read_text(encoding="utf-8"))
    assert _comparable(actual) == _comparable(expected)


def test_summarize_file_does_not_write(sample_scan_path, tmp_settings):
    result = summarize_file(sample_scan_path, settings=tmp_settings)
    assert isinstance(result, RunResult)
    assert result.output_path is None
    assert result.narrator_used is False
    assert result.warnings == []
    assert not tmp_settings.output_dir.exists()
    assert not tmp_settings.audit_log_path.exists()


def test_narrator_text_is_used_when_grounded(sample_scan_path, tmp_settings):
    seen = []

    def narrator(summary):
        seen.append(summary.overview.hosts_total)
        return f"  {GOOD_TEXT}\n"

    result = run(sample_scan_path, settings=tmp_settings, narrator=narrator)
    assert seen == [5]
    assert result.narrator_used is True
    assert result.warnings == []
    written = json.loads(result.output_path.read_text(encoding="utf-8"))
    assert written["overview"]["summary_text"] == GOOD_TEXT
    assert _audit_events(tmp_settings)[0]["summary_text_source"] == "narrator"


def test_narrator_exception_falls_back_to_template(sample_scan_path, tmp_settings):
    def narrator(summary):
        raise TimeoutError("model took too long")

    result = summarize_file(sample_scan_path, settings=tmp_settings, narrator=narrator)
    assert result.narrator_used is False
    assert result.summary.overview.summary_text.startswith("5 hosts listed")
    assert result.warnings == [
        "narrator failed (TimeoutError: model took too long); kept template text"
    ]


@pytest.mark.parametrize(
    "bad_text,expected",
    [
        ("web01.lab.local is exposed to CVE-2021-44228.", "CVE-2021-44228 is not in the scan"),
        ("Host 10.10.20.77 runs SSH.", "IP address 10.10.20.77 is not in the scan"),
        ("Host 10.10.20.5 runs SSH.", "IP address 10.10.20.5 names an individual host"),
        ("Three of five hosts are up.", "the scan has 4 host(s) up"),
        ("", "text is empty"),
    ],
)
def test_hallucinating_narrator_falls_back(sample_scan_path, tmp_settings, bad_text, expected):
    result = run(sample_scan_path, settings=tmp_settings, narrator=lambda s: bad_text)

    assert result.narrator_used is False
    assert len(result.warnings) == 1
    assert "narrator text rejected" in result.warnings[0]
    assert expected in result.warnings[0]
    written = json.loads(result.output_path.read_text(encoding="utf-8"))
    assert written["overview"]["summary_text"].startswith("5 hosts listed")
    assert "CVE" not in json.dumps(written)
    event = _audit_events(tmp_settings)[0]
    assert event["outcome"] == "ok"
    assert event["warnings"] == result.warnings


def test_non_text_narrator_result_falls_back(sample_scan_path, tmp_settings):
    result = summarize_file(sample_scan_path, settings=tmp_settings, narrator=lambda s: None)
    assert result.narrator_used is False
    assert result.warnings == ["narrator returned NoneType, not text; kept template text"]


def test_audit_event_on_success(sample_scan_path, tmp_settings):
    result = run(sample_scan_path, settings=tmp_settings)
    events = _audit_events(tmp_settings)
    assert len(events) == 1
    event = events[0]
    assert event["step"] == "recon_summarize"
    assert event["outcome"] == "ok"
    assert event["input_file"] == str(sample_scan_path)
    assert len(event["input_sha256"]) == 64
    assert event["problems"] == []
    assert event["warnings"] == []
    assert event["narrator_used"] is False
    assert event["flagged_note_counts"] == {"possible_prompt_injection": 0, "truncated": 0}
    assert (event["hosts_total"], event["open_ports_total"]) == (5, 6)
    assert event["output_path"] == str(result.output_path)
    assert event["timestamp"]
    assert event["event_id"]


def test_audit_counts_flagged_notes(tmp_settings):
    run(SCANS_DIR / "sample_scan_02.json", settings=tmp_settings)
    event = _audit_events(tmp_settings)[0]
    assert event["flagged_note_counts"] == {"possible_prompt_injection": 3, "truncated": 1}


def test_audit_event_on_load_failure(tmp_path, tmp_settings):
    with pytest.raises(ScanLoadError):
        run(tmp_path / "missing.json", settings=tmp_settings)

    event = _audit_events(tmp_settings)[0]
    assert event["outcome"] == "load_error"
    assert event["input_sha256"] is None
    assert event["output_path"] is None
    assert len(event["problems"]) == 1
    assert event["problems"][0].startswith("ScanLoadError: ")


def test_audit_event_on_malformed_file(tmp_path, tmp_settings):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(ScanLoadError):
        run(bad, settings=tmp_settings)
    event = _audit_events(tmp_settings)[0]
    assert event["outcome"] == "load_error"
    assert len(event["input_sha256"]) == 64


def test_validation_failure_is_audited_and_nothing_written(
    sample_scan_path, tmp_settings, monkeypatch
):
    monkeypatch.setattr(pipeline, "validate_summary", lambda summary, scan: ["boom"])
    with pytest.raises(SummaryValidationError) as excinfo:
        run(sample_scan_path, settings=tmp_settings)

    assert excinfo.value.problems == ["boom"]
    assert not tmp_settings.output_dir.exists()
    event = _audit_events(tmp_settings)[0]
    assert (event["outcome"], event["problems"], event["hosts_total"]) == (
        "validation_error",
        ["boom"],
        5,
    )


def test_summarize_file_raises_on_validation_failure(sample_scan_path, tmp_settings, monkeypatch):
    monkeypatch.setattr(pipeline, "validate_summary", lambda summary, scan: ["a", "b"])
    with pytest.raises(SummaryValidationError, match="- a\n- b") as excinfo:
        summarize_file(sample_scan_path, settings=tmp_settings)
    assert excinfo.value.problems == ["a", "b"]


def test_unexpected_error_is_audited(sample_scan_path, tmp_settings, monkeypatch):
    def broken_write(*args, **kwargs):
        raise PermissionError("read-only output")

    monkeypatch.setattr(pipeline, "write_output", broken_write)
    with pytest.raises(PermissionError):
        run(sample_scan_path, settings=tmp_settings)
    event = _audit_events(tmp_settings)[0]
    assert event["outcome"] == "error"
    assert event["problems"] == ["PermissionError: read-only output"]


def test_audit_log_is_appended_across_runs(sample_scan_path, tmp_settings):
    run(sample_scan_path, settings=tmp_settings)
    run(sample_scan_path, settings=tmp_settings)
    assert len(_audit_events(tmp_settings)) == 2


def test_output_dir_argument_overrides_settings(sample_scan_path, tmp_settings, tmp_path):
    result = run(sample_scan_path, tmp_path / "custom", settings=tmp_settings)
    assert result.output_path == tmp_path / "custom" / "sample_scan_01.summary.json"
