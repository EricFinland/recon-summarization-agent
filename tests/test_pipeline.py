"""Golden test for the full agent. Remove the xfail marker once the pipeline works."""

import json

import pytest

from recon_agent.pipeline import run


@pytest.mark.xfail(raises=NotImplementedError, strict=True, reason="agent not built yet")
def test_sample_scan_matches_expected_summary(tmp_path, sample_scan_path, expected_summary):
    out = run(sample_scan_path, tmp_path)
    actual = json.loads(out.read_text())

    # generated_at and summary_text are free-form; compare everything else exactly.
    for doc in (actual, expected_summary):
        doc.pop("generated_at")
        doc["overview"].pop("summary_text")
    assert actual == expected_summary
