import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_SCAN = ROOT / "data" / "scans" / "sample_scan_01.json"
EXPECTED_SUMMARY = ROOT / "schemas" / "examples" / "sample_scan_01.summary.json"


@pytest.fixture
def schema() -> dict:
    return json.loads((ROOT / "schemas" / "recon_summary.schema.json").read_text())


@pytest.fixture
def sample_scan_path() -> Path:
    return SAMPLE_SCAN


@pytest.fixture
def sample_scan() -> dict:
    return json.loads(SAMPLE_SCAN.read_text())


@pytest.fixture
def expected_summary() -> dict:
    return json.loads(EXPECTED_SUMMARY.read_text())
