"""Check a summary against the source scan data and the output schema.

validate_summary() is the gate before anything is written: every host, port,
observation, and count must trace back to the input, the output must match the
JSON Schema, and no CVE identifier may appear that the input does not contain.
check_summary_text() is the grounding check for free text such as a narrator's
summary_text. That text is an aggregate overview: it may not name individual
hosts, and every number in it must be one of the scan's aggregate counts. The
check is lexical and numeric; it cannot prove that each sentence is true.
"""

import ipaddress
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from recon_agent.facts import aggregate_facts, fact_numbers
from recon_agent.models import HostSummary, ReconSummary, ScanHost, ScanPort, ScanResult
from recon_agent.sanitizer import check_note
from recon_agent.summarizer import summarize

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "recon_summary.schema.json"
MAX_SUMMARY_TEXT_CHARS = 1200

CVE_RE = re.compile(r"CVE-\d{4}-\d{4,}", re.IGNORECASE)
_EVIDENCE_RE = re.compile(r"hosts\[(\d+)\]\.notes\[(\d+)\]")
_IPV4_RE = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?!\w|\.\d)")
_IPV6_RE = re.compile(r"(?<![\w:.])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?![\w:])")
_COUNT_WORDS = r"(?:hosts?|ports?|services?|notes?|observations?|addresses|of|out)"
_PORT_LIST_RE = re.compile(
    r"\bports?\s+(?:number\s+)?#?(\d{1,5}\b(?:(?:\s*[,/]\s*|\s*,?\s+(?:and|or)\s+)\d{1,5}\b"
    rf"(?!\s*{_COUNT_WORDS}\b))*)",
    re.IGNORECASE,
)
_PORT_PROTO_RE = re.compile(
    r"(?<![\w.])(\d{1,5})\s*/\s*(?:tcp|udp)\b|\b(?:tcp|udp)\s*/\s*(\d{1,5})\b", re.IGNORECASE
)
_PORT_SUFFIX_RE = re.compile(r"(?<![\w.-])[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+:(\d{1,5})\b")
_HOSTNAME_RE = re.compile(
    r"(?<![\w.@-])(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}(?!\.?[\w-])"
)
_FILE_SUFFIXES = {"json", "xml", "txt", "log", "csv"}
# Hyphenated identifiers such as "microsoft-ds" or "ms-wbt-server" (not dates).
_HYPHENATED_RE = re.compile(r"(?<![\w.-])[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+(?![\w-])")
_COMMON_HYPHENATED = frozenset(
    {"instruction-like", "non-open", "well-known", "open-source", "high-level", "low-level"}
)
_VERSION_RE = re.compile(r"(?<![\w.])\d+(?:\.\d+)+[A-Za-z0-9]*")
_IP_OR_CIDR_RE = re.compile(rf"(?:{_IPV4_RE.pattern}|{_IPV6_RE.pattern})(?:/\d{{1,3}})?")
_DATE_RE = re.compile(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)")
_TIME_RE = re.compile(r"(?<!\d)\d{1,2}:\d{2}(?::\d{2})?(?!\d)")
_NUMBER_WORDS = {
    word: value
    for value, word in enumerate(
        "zero one two three four five six seven eight nine ten eleven twelve thirteen "
        "fourteen fifteen sixteen seventeen eighteen nineteen twenty".split()
    )
}
_NUM = rf"(?:\d+|{'|'.join(_NUMBER_WORDS)})"
_NUMBER_RE = re.compile(rf"(?<![\w.]){_NUM}(?!\w)", re.IGNORECASE)
# Status claims such as "4 of 5 hosts are up", "one host is down", "4 up", and
# "1 down" (but not "1 up host had no open ports").
_STATUS_WORDS = {"up": "up", "online": "up", "down": "down", "offline": "down"}
_STATUS = rf"(?P<status>{'|'.join(_STATUS_WORDS)})\b(?!\s+hosts?\b)"
_STATUS_CLAIM_RES = (
    re.compile(
        rf"(?<![\w.])(?P<n>{_NUM})\s+(?:(?:out\s+)?of\s+(?:the\s+|all\s+)?(?P<m>{_NUM})\s+)?"
        rf"(?:[a-z]+\s+)?hosts?\s+(?:[a-z]+\s+){{0,2}}{_STATUS}",
        re.IGNORECASE,
    ),
    re.compile(rf"(?<![\w.])(?P<n>{_NUM})\s+(?:(?:are|were|is|was)\s+)?{_STATUS}", re.IGNORECASE),
)
# "6 open ports across 3 hosts"
_ACROSS_CLAIM_RE = re.compile(
    rf"(?<![\w.])(?P<n>{_NUM})\s+open\s+(?:(?:tcp|udp)\s+)?ports?\s+across\s+"
    rf"(?P<m>{_NUM})\s+hosts?\b",
    re.IGNORECASE,
)
# Words that assess risk. The recon agent only restates the scan, so these may
# appear in narrative text only if the scan itself uses them.
_RISK_STEMS = {
    "vulnerab": re.compile(r"\bvulnerab\w*", re.IGNORECASE),
    "exploit": re.compile(r"\bexploit\w*", re.IGNORECASE),
    "cvss": re.compile(r"\bcvss\b", re.IGNORECASE),
    "severity": re.compile(r"\bseverit\w*", re.IGNORECASE),
    "critical": re.compile(r"\bcritical\w*", re.IGNORECASE),
    "compromise": re.compile(r"\bcompromis\w*", re.IGNORECASE),
    "malware": re.compile(r"\bmalware\b", re.IGNORECASE),
    "backdoor": re.compile(r"\bbackdoor\w*", re.IGNORECASE),
}


@lru_cache(maxsize=1)
def _schema_validator() -> Draft202012Validator:
    """Load the output JSON Schema once."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)


def validate_summary(summary: ReconSummary, scan: ScanResult) -> list[str]:
    """Return a list of problems (an empty list means the summary is valid)."""
    data = summary.model_dump(mode="json")
    problems = [
        f"schema: {'/'.join(map(str, err.absolute_path)) or '(root)'}: {err.message}"
        for err in _schema_validator().iter_errors(data)
    ]
    if summary.generated_at.tzinfo is None:
        problems.append("generated_at must be timezone-aware (UTC)")
    problems += _check_source(summary, scan)
    problems += _check_overview(summary, scan)
    problems += _check_hosts(summary, scan)

    input_cves = {cve.upper() for cve in CVE_RE.findall(scan.model_dump_json())}
    output_cves = {cve.upper() for cve in CVE_RE.findall(json.dumps(data))}
    problems += [
        f"{cve} appears in the output but not in the input"
        for cve in sorted(output_cves - input_cves)
    ]

    problems += [
        f"overview.summary_text: {problem}"
        for problem in check_summary_text(summary.overview.summary_text, scan)
    ]
    return problems


def _check_source(summary: ReconSummary, scan: ScanResult) -> list[str]:
    """Check the source block against the scan."""
    problems = []
    source = summary.source
    if not source.scan_file or "/" in source.scan_file or "\\" in source.scan_file:
        problems.append(f"source.scan_file {source.scan_file!r} must be a bare file name")
    if source.scan_id != scan.scan_id:
        problems.append(f"source.scan_id is {source.scan_id!r} but the input has {scan.scan_id!r}")
    if source.target_range != scan.target_range:
        problems.append(
            f"source.target_range is {source.target_range!r} "
            f"but the input has {scan.target_range!r}"
        )
    return problems


def _check_overview(summary: ReconSummary, scan: ScanResult) -> list[str]:
    """Check overview counts against the scan."""
    expected = {
        "hosts_total": len(scan.hosts),
        "hosts_up": sum(host.status == "up" for host in scan.hosts),
        "open_ports_total": sum(p.state == "open" for host in scan.hosts for p in host.ports),
    }
    return [
        f"overview.{name} is {getattr(summary.overview, name)} but the input gives {value}"
        for name, value in expected.items()
        if getattr(summary.overview, name) != value
    ]


def _check_hosts(summary: ReconSummary, scan: ScanResult) -> list[str]:
    """Check that hosts match the input one to one, in order."""
    problems = []
    for index, (out, inp) in enumerate(zip(summary.hosts, scan.hosts, strict=False)):
        label = f"hosts[{index}]"
        for name in ("ip", "hostname", "status", "os_guess"):
            got, want = getattr(out, name), getattr(inp, name)
            if got != want:
                problems.append(f"{label}.{name} is {got!r} but the input has {want!r}")
        problems += _check_ports(label, out, inp)
        problems += _check_observations(index, out, inp)
    for index in range(len(scan.hosts), len(summary.hosts)):
        problems.append(f"hosts[{index}] ({summary.hosts[index].ip}) is not in the input")
    for index in range(len(summary.hosts), len(scan.hosts)):
        problems.append(
            f"input hosts[{index}] ({scan.hosts[index].ip}) is missing from the summary"
        )
    return problems


def _check_ports(label: str, out: HostSummary, inp: ScanHost) -> list[str]:
    """Check open_ports and other_ports against the input host's ports."""
    expected_open = [
        p.model_dump(include={"port", "protocol", "service", "product", "version"})
        for p in inp.ports
        if p.state == "open"
    ]
    expected_other = [
        p.model_dump(include={"port", "protocol", "state", "service"})
        for p in inp.ports
        if p.state != "open"
    ]
    return _compare_ports(
        f"{label}.open_ports",
        [p.model_dump() for p in out.open_ports],
        expected_open,
        inp.ports,
        "an open port",
    ) + _compare_ports(
        f"{label}.other_ports",
        [p.model_dump() for p in out.other_ports],
        expected_other,
        inp.ports,
        "a non-open port",
    )


def _compare_ports(
    label: str,
    actual: list[dict[str, Any]],
    expected: list[dict[str, Any]],
    input_ports: list[ScanPort],
    kind: str,
) -> list[str]:
    """Explain how `actual` differs from `expected` (both in input order)."""
    if actual == expected:
        return []
    problems = []
    by_key: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for item in expected:
        by_key[(item["port"], item["protocol"])].append(item)
    states = {(p.port, p.protocol): p.state for p in input_ports}

    for index, item in enumerate(actual):
        key = (item["port"], item["protocol"])
        name = f"{label}[{index}] ({key[0]}/{key[1]})"
        candidates = by_key.get(key)
        if not candidates:
            state = states.get(key)
            detail = f" (input state is {state!r})" if state else ""
            problems.append(f"{name} is not {kind} in the input{detail}")
        elif item not in candidates:
            want = candidates[0]
            diffs = [
                f"{k} is {item.get(k)!r} but the input has {want[k]!r}"
                for k in want
                if item.get(k) != want[k]
            ]
            problems.append(f"{name}: {'; '.join(diffs)}")

    got_keys = Counter((item["port"], item["protocol"]) for item in actual)
    want_keys = Counter((item["port"], item["protocol"]) for item in expected)
    for key, count in want_keys.items():
        if got_keys[key] < count:
            problems.append(f"{label}: input port {key[0]}/{key[1]} is missing")
        elif got_keys[key] > count:
            problems.append(f"{label}: port {key[0]}/{key[1]} is listed more times than the input")
    if not problems:
        problems.append(f"{label}: ports are not in input order")
    return problems


def _check_observations(index: int, out: HostSummary, inp: ScanHost) -> list[str]:
    """Check that observations map one to one onto the host's non-empty notes."""
    problems = []
    seen: Counter[int] = Counter()
    for obs_index, obs in enumerate(out.observations):
        name = f"hosts[{index}].observations[{obs_index}]"
        match = _EVIDENCE_RE.fullmatch(obs.evidence)
        if match is None:
            problems.append(
                f"{name}: evidence {obs.evidence!r} is not of the form hosts[N].notes[M]"
            )
            continue
        host_index, note_index = int(match.group(1)), int(match.group(2))
        if host_index != index:
            problems.append(f"{name}: evidence {obs.evidence!r} points to a different host")
            continue
        if note_index >= len(inp.notes) or not inp.notes[note_index].strip():
            problems.append(f"{name}: evidence {obs.evidence!r} does not resolve to an input note")
            continue
        seen[note_index] += 1
        check = check_note(inp.notes[note_index])
        if obs.text != check.text:
            problems.append(f"{name}: text does not match the input note at {obs.evidence}")
        if list(obs.flags) != list(check.flags):
            problems.append(f"{name}: flags {list(obs.flags)} should be {list(check.flags)}")

    for note_index, note in enumerate(inp.notes):
        if note.strip() and seen[note_index] == 0:
            problems.append(f"hosts[{index}].notes[{note_index}] has no observation")
        elif seen[note_index] > 1:
            problems.append(f"hosts[{index}].notes[{note_index}] has more than one observation")

    order = list(seen.elements())
    if not problems and order != sorted(order):
        problems.append(f"hosts[{index}].observations are not in input note order")
    return problems


@dataclass
class _Mentions:
    """Checkable facts mentioned in a piece of text."""

    ips: set[str] = field(default_factory=set)
    cves: set[str] = field(default_factory=set)
    ports: set[int] = field(default_factory=set)
    versions: set[str] = field(default_factory=set)
    hostnames: set[str] = field(default_factory=set)
    risk_terms: dict[str, str] = field(default_factory=dict)


def _mentions(text: str) -> _Mentions:
    """Extract IPs, CVEs, ports in a port context, versions, hostnames, and risk terms."""
    found = _Mentions()
    found.cves = {cve.upper() for cve in CVE_RE.findall(text)}
    for match in _PORT_LIST_RE.finditer(text):
        found.ports.update(int(n) for n in re.findall(r"\d+", match.group(1)))
    for match in _PORT_PROTO_RE.finditer(text):
        found.ports.add(int(match.group(1) or match.group(2)))
    found.ports.update(int(m.group(1)) for m in _PORT_SUFFIX_RE.finditer(text))
    for stem, pattern in _RISK_STEMS.items():
        match = pattern.search(text)
        if match:
            found.risk_terms[stem] = match.group()

    def take_ip(match: re.Match[str]) -> str:
        try:
            found.ips.add(str(ipaddress.ip_address(match.group())))
        except ValueError:
            return match.group()
        return " "

    rest = _IPV6_RE.sub(take_ip, _IPV4_RE.sub(take_ip, text))
    found.hostnames = {
        name.lower()
        for name in _HOSTNAME_RE.findall(rest)
        if name.rsplit(".", 1)[1].lower() not in _FILE_SUFFIXES
    }
    found.versions = {version.lower() for version in _VERSION_RE.findall(rest)}
    return found


def _scan_text(scan: ScanResult) -> str:
    """Return every published string in the scan, one per line.

    Notes contribute their published text (check_note), so a withheld
    instruction-like note cannot vouch for anything.
    """
    texts = [scan.scan_id, scan.scanner, scan.scan_type, scan.target_range]
    for host in scan.hosts:
        texts += [host.ip, host.hostname, host.os_guess]
        texts += [check_note(note).text for note in host.notes]
        for port in host.ports:
            texts += [port.service, port.product, port.version]
    return "\n".join(t for t in texts if t)


def _identifier_problems(text: str, scan: ScanResult) -> list[str]:
    """Report hyphenated identifiers (e.g. "microsoft-ds") that the scan does not contain.

    Service and product names are often hyphenated, and a model that garbles
    one ("Microsoft-DNS" for "microsoft-ds") invents a service. Ordinary
    hyphenated words are allowed only from a short list.
    """
    known = _scan_text(scan).lower()
    return [
        f"name {token!r} is not in the scan"
        for token in dict.fromkeys(_HYPHENATED_RE.findall(text))
        if token.lower() not in _COMMON_HYPHENATED and token.lower() not in known
    ]


def _scan_facts(scan: ScanResult) -> _Mentions:
    """Collect every fact the scan supports, from its fields and its free text."""
    facts = _mentions(_scan_text(scan))
    for host in scan.hosts:
        facts.ips.add(str(ipaddress.ip_address(host.ip)))
        if host.hostname:
            facts.hostnames.add(host.hostname.lower())
        for port in host.ports:
            facts.ports.add(port.port)
            if port.version:
                facts.versions.add(port.version.lower())
    return facts


def _number_value(token: str) -> int:
    """Return the value of a digit string or a number word."""
    return int(token) if token.isdigit() else _NUMBER_WORDS[token.lower()]


def _without_target_range(text: str, target_range: str | None) -> str:
    """Blank out the scan's target range (and each range it lists) wherever it appears."""
    if not target_range:
        return text
    parts = {target_range, *re.split(r"[,;\s]+", target_range)} - {""}
    for part in sorted(parts, key=len, reverse=True):
        text = re.sub(re.escape(part), " ", text, flags=re.IGNORECASE)
    return text


def _host_mentions(text: str, scan: ScanResult) -> list[str]:
    """Report host IPs and hostnames in `text`: summary_text is aggregate only."""
    host_ips = {str(ipaddress.ip_address(host.ip)) for host in scan.hosts}
    problems = [
        f"IP address {ip} names an individual host; summary_text must stay aggregate"
        for ip in sorted(_mentions(text).ips & host_ips)
    ]
    names: set[str] = set()
    for host in scan.hosts:
        if not host.hostname:
            continue
        hostname = host.hostname.lower()
        names.add(hostname)
        # Also the short name (e.g. "web01"), when it cannot be an ordinary word.
        label = hostname.split(".", 1)[0]
        if label != hostname and re.search(r"\d", label) and re.search(r"[a-z]", label):
            names.add(label)
    lowered = text.lower()
    problems += [
        f"hostname {name} names an individual host; summary_text must stay aggregate"
        for name in sorted(names)
        if re.search(rf"(?<![\w.-]){re.escape(name)}(?![\w-]|\.[\w-])", lowered)
    ]
    return problems


def _blank_checked_tokens(text: str, facts: dict[str, Any]) -> str:
    """Blank out tokens whose digits are not counts.

    These are IPs, CIDRs, CVE ids, dates, times, hostnames, versions, ports in a
    port context, and fact strings such as "Windows Server 2019". Each kind is
    checked separately.
    """
    spans: list[tuple[int, int]] = []
    for pattern in (
        CVE_RE,
        _IP_OR_CIDR_RE,
        _DATE_RE,
        _TIME_RE,
        _HOSTNAME_RE,
        _VERSION_RE,
        _PORT_PROTO_RE,
    ):
        spans += [match.span() for match in pattern.finditer(text)]
    spans += [match.span(1) for match in _PORT_LIST_RE.finditer(text)]
    spans += [match.span(1) for match in _PORT_SUFFIX_RE.finditer(text)]
    for key in ("open_services", "open_products", "os_guesses"):
        for value in facts[key]:
            if re.search(r"[A-Za-z]", value):
                pattern = re.compile(rf"(?<!\w){re.escape(value)}(?!\w)", re.IGNORECASE)
                spans += [match.span() for match in pattern.finditer(text)]
    chars = list(text)
    for begin, end in spans:
        chars[begin:end] = " " * (end - begin)
    return "".join(chars)


def _number_problems(text: str, facts: dict[str, Any]) -> list[str]:
    """Check that every number in `text` is one of the scan's aggregate counts."""
    text = _blank_checked_tokens(text, facts)
    allowed = fact_numbers(facts)
    problems = [
        f"number {match.group()!r} does not match any count in the scan"
        for match in _NUMBER_RE.finditer(text)
        if _number_value(match.group()) not in allowed
    ]

    status_counts = {"up": facts["hosts_up"], "down": facts["hosts_down"]}
    for pattern in _STATUS_CLAIM_RES:
        for match in pattern.finditer(text):
            claim = " ".join(match.group().split())
            status = _STATUS_WORDS[match.group("status").lower()]
            if _number_value(match.group("n")) != status_counts[status]:
                problems.append(f"{claim!r}: the scan has {status_counts[status]} host(s) {status}")
            total = match.groupdict().get("m")
            if total is not None and _number_value(total) != facts["hosts_total"]:
                problems.append(f"{claim!r}: the scan lists {facts['hosts_total']} host(s)")
    for match in _ACROSS_CLAIM_RE.finditer(text):
        claim = " ".join(match.group().split())
        if _number_value(match.group("n")) != facts["open_ports_total"]:
            problems.append(f"{claim!r}: the scan has {facts['open_ports_total']} open port(s)")
        if _number_value(match.group("m")) != facts["hosts_with_open_ports"]:
            problems.append(f"{claim!r}: {facts['hosts_with_open_ports']} host(s) have open ports")
    return list(dict.fromkeys(problems))


def check_summary_text(text: str, scan: ScanResult) -> list[str]:
    """Return problems with narrative `text` that the scan does not support.

    Every IP, hostname, port, version, and CVE id must be in the scan. The text
    must also stay aggregate: no host IP or hostname may appear (the target
    range may), and every number must be one of the counts in
    `facts.aggregate_facts` or a scan port in a port context.
    """
    if not text.strip():
        return ["text is empty"]
    problems = []
    if len(text) > MAX_SUMMARY_TEXT_CHARS:
        problems.append(f"text is {len(text)} characters (limit {MAX_SUMMARY_TEXT_CHARS})")
    facts = _scan_facts(scan)
    found = _mentions(text)
    problems += [f"IP address {ip} is not in the scan" for ip in sorted(found.ips - facts.ips)]
    problems += [f"{cve} is not in the scan" for cve in sorted(found.cves - facts.cves)]
    problems += [f"port {port} is not in the scan" for port in sorted(found.ports - facts.ports)]
    problems += [
        f"version {version} is not in the scan"
        for version in sorted(found.versions)
        if not any(known == version or known.startswith(version + ".") for known in facts.versions)
    ]
    problems += [
        f"hostname {name} is not in the scan"
        for name in sorted(found.hostnames)
        if not any(known == name or known.endswith("." + name) for known in facts.hostnames)
    ]
    problems += [
        f"term {word!r} assesses risk, which the scan does not support"
        for stem, word in found.risk_terms.items()
        if stem not in facts.risk_terms
    ]
    rest = _without_target_range(text, scan.target_range)
    problems += _identifier_problems(rest, scan)
    problems += _host_mentions(rest, scan)
    problems += _number_problems(rest, aggregate_facts(summarize(scan, "scan")))
    return problems
