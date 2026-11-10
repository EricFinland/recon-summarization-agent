import json
from pathlib import Path

import pytest

from recon_agent.config import Settings

ROOT = Path(__file__).resolve().parent.parent
SCANS_DIR = ROOT / "data" / "scans"
EXAMPLES_DIR = ROOT / "schemas" / "examples"
SAMPLE_SCAN = SCANS_DIR / "sample_scan_01.json"
EXPECTED_SUMMARY = EXAMPLES_DIR / "sample_scan_01.summary.json"


def _example_pairs() -> list[tuple[Path, Path | None]]:
    """Pair each schemas/examples/<stem>.summary.json with data/scans/<stem>.<any extension>."""
    pairs = []
    for example in sorted(EXAMPLES_DIR.glob("*.summary.json")):
        stem = example.name.removesuffix(".summary.json")
        scans = sorted(p for p in SCANS_DIR.glob(f"{stem}.*") if p.is_file())
        pairs.append((example, scans[0] if len(scans) == 1 else None))
    return pairs


# (example summary, matching scan file or None if missing/ambiguous)
EXAMPLE_PAIRS = _example_pairs()
SAMPLE_SCANS = sorted(p for p in SCANS_DIR.iterdir() if p.suffix in {".json", ".xml"})


@pytest.fixture
def schema() -> dict:
    return json.loads((ROOT / "schemas" / "recon_summary.schema.json").read_text(encoding="utf-8"))


@pytest.fixture
def sample_scan_path() -> Path:
    return SAMPLE_SCAN


@pytest.fixture
def sample_scan() -> dict:
    return json.loads(SAMPLE_SCAN.read_text(encoding="utf-8"))


@pytest.fixture
def expected_summary() -> dict:
    return json.loads(EXPECTED_SUMMARY.read_text(encoding="utf-8"))


@pytest.fixture
def tmp_settings(tmp_path) -> Settings:
    """Settings that keep every output and the audit log inside tmp_path."""
    return Settings(
        output_dir=tmp_path / "out",
        audit_log_path=tmp_path / "audit" / "audit.log.jsonl",
    )
