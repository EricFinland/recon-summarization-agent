"""Keep the schema, the example outputs, and the sample inputs consistent."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from recon_agent.loader import load_scan
from tests.conftest import EXAMPLE_PAIRS

IDS = [example.name for example, _ in EXAMPLE_PAIRS]


def test_schema_is_valid(schema):
    Draft202012Validator.check_schema(schema)


def test_every_example_has_one_scan_file():
    assert EXAMPLE_PAIRS, "no examples found"
    assert [example.name for example, scan in EXAMPLE_PAIRS if scan is None] == []


@pytest.mark.parametrize("example,scan_path", EXAMPLE_PAIRS, ids=IDS)
def test_example_summary_matches_schema(schema, example: Path, scan_path: Path | None):
    document = json.loads(example.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
    assert [e.message for e in validator.iter_errors(document)] == []


@pytest.mark.parametrize("example,scan_path", EXAMPLE_PAIRS, ids=IDS)
def test_example_summary_matches_sample_input(example: Path, scan_path: Path | None):
    assert scan_path is not None
    scan = load_scan(scan_path)
    expected = json.loads(example.read_text(encoding="utf-8"))
    overview = expected["overview"]

    assert overview["hosts_total"] == len(scan.hosts)
    assert overview["hosts_up"] == sum(h.status == "up" for h in scan.hosts)
    assert overview["open_ports_total"] == sum(
        p.state == "open" for h in scan.hosts for p in h.ports
    )
    assert [h["ip"] for h in expected["hosts"]] == [h.ip for h in scan.hosts]
    assert expected["source"]["scan_file"] == scan_path.name
