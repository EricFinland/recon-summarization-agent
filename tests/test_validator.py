"""Validator tests: a correct summary passes, and every kind of tampering is caught."""

from collections.abc import Callable
from pathlib import Path

import pytest

from recon_agent.loader import load_scan
from recon_agent.models import OpenPort, ReconSummary, ScanResult
from recon_agent.summarizer import summarize
from recon_agent.validator import MAX_SUMMARY_TEXT_CHARS, check_summary_text, validate_summary

SCANS = Path(__file__).resolve().parent.parent / "data" / "scans"

GOOD_NARRATIVE = (
    "The scan of 10.10.20.0/24 lists five hosts, four of them up and one down. "
    "It found 6 open ports across 3 hosts, running ssh, http, https, mysql, microsoft-ds, "
    "and ms-wbt-server; nginx 1.18.0 serves two of them, alongside OpenSSH 8.9p1 and "
    "MySQL 5.7.38. Operating system guesses are Linux 5.x and Windows Server 2019, and "
    "the scan ran on 2026-11-01 from 14:00."
)

# The exact sentence a local model produced in a live run. Both claims are false:
# 10.10.20.30 has an OS guess and two open ports, and 10.10.20.99 is down.
HALLUCINATED_SENTENCE = (
    "The other two hosts, 10.10.20.30 and 10.10.20.99, are up but their operating "
    "systems and open ports are not specified."
)


@pytest.fixture(scope="module")
def scan() -> ScanResult:
    return load_scan(SCANS / "sample_scan_01.json")


@pytest.fixture(scope="module")
def scan02() -> ScanResult:
    return load_scan(SCANS / "sample_scan_02.json")


@pytest.fixture
def summary(scan) -> ReconSummary:
    return summarize(scan, "sample_scan_01.json")


def _problems_after(summary: ReconSummary, scan: ScanResult, tamper: Callable) -> list[str]:
    tampered = summary.model_copy(deep=True)
    tamper(tampered)
    return validate_summary(tampered, scan)


def test_untampered_summary_is_valid(summary, scan):
    assert validate_summary(summary, scan) == []


def test_untampered_summary_with_injection_notes_is_valid(scan02):
    assert validate_summary(summarize(scan02, "sample_scan_02.json"), scan02) == []


def _extra_host(s):
    s.hosts.append(s.hosts[0].model_copy(update={"ip": "10.10.20.200"}))


def _swap_ports(s):
    s.hosts[0].open_ports.reverse()


def _swap_observations(s):
    s.hosts[0].observations.reverse()


def _open_filtered_port(s):
    s.hosts[0].open_ports.append(
        OpenPort(port=8080, protocol="tcp", service="http-proxy", product=None, version=None)
    )


TAMPERS = {
    "extra host": (_extra_host, "hosts[5] (10.10.20.200) is not in the input"),
    "missing host": (lambda s: s.hosts.pop(), "input hosts[4] (10.10.20.99) is missing"),
    "changed hostname": (
        lambda s: setattr(s.hosts[2], "hostname", "dc01.lab.local"),
        "hosts[2].hostname is 'dc01.lab.local' but the input has None",
    ),
    "invented os_guess": (
        lambda s: setattr(s.hosts[1], "os_guess", "Ubuntu 22.04"),
        "hosts[1].os_guess",
    ),
    "fake port": (
        lambda s: s.hosts[3].open_ports.append(
            OpenPort(port=9999, protocol="tcp", service="abyss", product=None, version=None)
        ),
        "hosts[3].open_ports[0] (9999/tcp) is not an open port in the input",
    ),
    "filtered port shown as open": (_open_filtered_port, "input state is 'filtered'"),
    "altered version": (
        lambda s: setattr(s.hosts[0].open_ports[1], "version", "1.19.0"),
        "version is '1.19.0' but the input has '1.18.0'",
    ),
    "dropped port": (
        lambda s: s.hosts[1].other_ports.clear(),
        "hosts[1].other_ports: input port 22/tcp is missing",
    ),
    "port order": (_swap_ports, "hosts[0].open_ports: ports are not in input order"),
    "dropped note": (
        lambda s: s.hosts[0].observations.pop(),
        "hosts[0].notes[1] has no observation",
    ),
    "evidence out of range": (
        lambda s: setattr(s.hosts[0].observations[0], "evidence", "hosts[0].notes[7]"),
        "does not resolve to an input note",
    ),
    "evidence for another host": (
        lambda s: setattr(s.hosts[1].observations[0], "evidence", "hosts[0].notes[0]"),
        "points to a different host",
    ),
    "malformed evidence": (
        lambda s: setattr(s.hosts[0].observations[0], "evidence", "notes[0]"),
        "is not of the form hosts[N].notes[M]",
    ),
    "reworded note": (
        lambda s: setattr(s.hosts[2].observations[0], "text", "SMB signing disabled"),
        "hosts[2].observations[0]: text does not match the input note",
    ),
    "invented flag": (
        lambda s: setattr(s.hosts[2].observations[0], "flags", ["truncated"]),
        "flags ['truncated'] should be []",
    ),
    "observation order": (_swap_observations, "observations are not in input note order"),
    "fake CVE in observation": (
        lambda s: setattr(
            s.hosts[0].observations[1], "text", "TLS certificate expired; see CVE-2021-44228"
        ),
        "CVE-2021-44228 appears in the output but not in the input",
    ),
    "fake CVE in summary_text": (
        lambda s: setattr(s.overview, "summary_text", "Host 10.10.20.5 has cve-2023-1234."),
        "overview.summary_text: CVE-2023-1234 is not in the scan",
    ),
    "wrong hosts_up": (
        lambda s: setattr(s.overview, "hosts_up", 5),
        "overview.hosts_up is 5 but the input gives 4",
    ),
    "wrong open_ports_total": (
        lambda s: setattr(s.overview, "open_ports_total", 7),
        "overview.open_ports_total is 7",
    ),
    "wrong scan_id": (
        lambda s: setattr(s.source, "scan_id", "synthetic-999"),
        "source.scan_id is 'synthetic-999'",
    ),
    "scan_file with a path": (
        lambda s: setattr(s.source, "scan_file", "../secret/sample_scan_01.json"),
        "must be a bare file name",
    ),
    "schema violation (status)": (
        lambda s: setattr(s.hosts[0], "status", "maybe"),
        "schema: hosts/0/status:",
    ),
    "schema violation (port range)": (
        lambda s: setattr(s.hosts[0].open_ports[0], "port", 70000),
        "schema: hosts/0/open_ports/0/port:",
    ),
    "empty summary_text": (
        lambda s: setattr(s.overview, "summary_text", "  "),
        "overview.summary_text: text is empty",
    ),
}


@pytest.mark.parametrize("tamper,expected", TAMPERS.values(), ids=TAMPERS.keys())
def test_tampering_is_caught(summary, scan, tamper, expected):
    problems = _problems_after(summary, scan, tamper)
    assert any(expected in problem for problem in problems), problems


def test_injection_flag_cannot_be_removed(scan02):
    summary = summarize(scan02, "sample_scan_02.json")
    raw_note = scan02.hosts[0].notes[1]

    def reveal(s):
        s.hosts[0].observations[1].text = raw_note
        s.hosts[0].observations[1].flags = []

    problems = _problems_after(summary, scan02, reveal)
    assert any("text does not match" in p for p in problems)
    assert any("flags [] should be ['possible_prompt_injection']" in p for p in problems)


def test_realistic_narrative_passes(summary, scan):
    assert check_summary_text(GOOD_NARRATIVE, scan) == []
    summary.overview.summary_text = GOOD_NARRATIVE
    assert validate_summary(summary, scan) == []


@pytest.mark.parametrize(
    "text",
    [
        "nginx 1.18 serves ports 80/443.",
        "All named hosts are in the lab.local domain.",
        "Open ports 22, 80 and 443 serve SSH and web traffic, and tcp/3306 is open.",
        "Three hosts have open ports and one host is down.",
        "Scanned 10.10.20.0/24 from sample_scan_01.json.",
        "Four of five hosts are up.",
        "4 of the 5 hosts were up and 1 was down; 1 up host had no open ports.",
        "No CVE ids or notes were withheld, and none were truncated.",
    ],
)
def test_sensible_variants_pass(scan, text):
    assert check_summary_text(text, scan) == []


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Host 10.10.20.7 is down.", "IP address 10.10.20.7 is not in the scan"),
        ("Port 8443 is open on web01.", "port 8443 is not in the scan"),
        ("Ports 22, 80 and 8081 are open.", "port 8081 is not in the scan"),
        ("Service on 25/tcp accepts mail.", "port 25 is not in the scan"),
        ("web01.lab.local:9090 answers.", "port 9090 is not in the scan"),
        ("web01 runs nginx 1.20.1.", "version 1.20.1 is not in the scan"),
        ("OpenSSH 9.6p1 is present.", "version 9.6p1 is not in the scan"),
        ("mail.lab.local relays mail.", "hostname mail.lab.local is not in the scan"),
        ("See CVE-2024-3094.", "CVE-2024-3094 is not in the scan"),
        ("MySQL is a critical exposure.", "term 'critical' assesses risk"),
        ("web01 is vulnerable to attack.", "term 'vulnerable' assesses risk"),
        ("", "text is empty"),
        ("x" * (MAX_SUMMARY_TEXT_CHARS + 1), "characters (limit 1200)"),
    ],
)
def test_ungrounded_text_is_flagged(scan, text, expected):
    problems = check_summary_text(text, scan)
    assert any(expected in problem for problem in problems), problems


def test_ipv6_addresses_are_grounded(scan02):
    assert check_summary_text("The scan covered 2001:db8:56::/64.", scan02) == []
    problems = check_summary_text("A host answered at 2001:DB8:56::99.", scan02)
    assert problems == ["IP address 2001:db8:56::99 is not in the scan"]
    problems = check_summary_text("SMTP runs at 2001:DB8:56::25.", scan02)
    assert problems == [
        "IP address 2001:db8:56::25 names an individual host; summary_text must stay aggregate"
    ]


def test_withheld_note_cannot_ground_text(scan02):
    # The withheld injection note says "critical" and "vulnerabilities"; that must
    # not make those words acceptable in narrative text.
    problems = check_summary_text("files01 has a critical vulnerability.", scan02)
    assert any("'critical'" in p for p in problems)
    assert any("'vulnerability'" in p for p in problems)


def test_published_note_text_grounds_text(scan02):
    assert check_summary_text("SNMP did not respond on 161/udp.", scan02) == []


# --------------------------------------------------------------------------
# summary_text is aggregate only: no host names, and numbers must match counts
# --------------------------------------------------------------------------


def test_hallucinated_host_sentence_is_rejected(scan):
    problems = check_summary_text(HALLUCINATED_SENTENCE, scan)
    assert "IP address 10.10.20.30 names an individual host" in problems[0]
    assert any("10.10.20.99 names an individual host" in p for p in problems)


def test_garbled_service_name_is_rejected(scan):
    # Seen in a live run: the model turned "microsoft-ds" into "Microsoft-DNS".
    text = "Open services include SSH, HTTP, MySQL, {}, and MS-WBT-Server."
    assert check_summary_text(text.format("Microsoft-DNS"), scan) == [
        "name 'Microsoft-DNS' is not in the scan"
    ]
    assert check_summary_text(text.format("microsoft-ds"), scan) == []


def _host_names(scan: ScanResult) -> list[str]:
    names = [host.ip for host in scan.hosts]
    names += [host.hostname for host in scan.hosts if host.hostname]
    # Short names are checked when they contain a digit (web01), not plain words (printer).
    labels = [host.hostname.split(".")[0] for host in scan.hosts if host.hostname]
    return names + [label for label in labels if any(c.isdigit() for c in label)]


@pytest.mark.parametrize("scan_path", sorted(SCANS.glob("sample_scan_0*")), ids=lambda p: p.name)
def test_every_host_ip_and_hostname_is_rejected(scan_path):
    scan = load_scan(scan_path)
    for name in _host_names(scan):
        problems = check_summary_text(f"Port scanning reached {name} today.", scan)
        assert any("names an individual host" in p for p in problems), (name, problems)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Three of five hosts are up.", "'Three of five hosts are up': the scan has 4 host(s) up"),
        ("3 of 5 hosts are up.", "the scan has 4 host(s) up"),
        ("Four of six hosts are up.", "the scan lists 5 host(s)"),
        ("Two hosts are down.", "the scan has 1 host(s) down"),
        ("The scan lists 5 hosts: 3 up, 2 down.", "the scan has 4 host(s) up"),
        ("Seven hosts were listed.", "number 'Seven' does not match any count"),
        ("There are 12 open services.", "number '12' does not match any count"),
        ("5 open ports across 3 hosts.", "the scan has 6 open port(s)"),
        ("6 open ports across 2 hosts.", "3 host(s) have open ports"),
    ],
)
def test_wrong_numbers_are_rejected(scan, text, expected):
    problems = check_summary_text(text, scan)
    assert any(expected in problem for problem in problems), problems


def test_digits_inside_checked_tokens_are_not_counts(scan):
    text = (
        "The 10.10.20.0/24 scan ran 2026-11-01 14:06:42 and saw Windows Server 2019, "
        "OpenSSH 8.9p1, and ports 3306 and 3389."
    )
    assert check_summary_text(text, scan) == []


def test_target_range_may_name_a_single_host():
    scan = ScanResult(
        target_range="10.0.0.5",
        hosts=[{"ip": "10.0.0.5", "status": "up"}],
    )
    assert check_summary_text("The scan of 10.0.0.5 lists 1 host, 1 up.", scan) == []
