"""Keep the schema, the example output, and the sample input consistent."""

from jsonschema import Draft202012Validator


def test_schema_is_valid(schema):
    Draft202012Validator.check_schema(schema)


def test_example_summary_matches_schema(schema, expected_summary):
    validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
    errors = [e.message for e in validator.iter_errors(expected_summary)]
    assert errors == []


def test_example_summary_matches_sample_input(sample_scan, expected_summary):
    hosts = sample_scan["hosts"]
    open_ports = [p for h in hosts for p in h["ports"] if p["state"] == "open"]
    overview = expected_summary["overview"]

    assert overview["hosts_total"] == len(hosts)
    assert overview["hosts_up"] == sum(h["status"] == "up" for h in hosts)
    assert overview["open_ports_total"] == len(open_ports)
    assert [h["ip"] for h in expected_summary["hosts"]] == [h["ip"] for h in hosts]
