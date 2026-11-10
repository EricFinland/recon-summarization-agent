"""Load a local scan-results file into a sanitized ScanResult.

The loader only reads one local file: no network access and no credentials.
Every problem is reported as a ScanLoadError with a message meant for the
person running the agent. Input values are not echoed back in full, so a
hostile file cannot smuggle text through error messages.

Supported formats (detected from the file content, not the extension):

JSON
    Our own format, see data/scans/sample_scan_01.json. Validated strictly
    against models.ScanResult (no type coercion, so "22" is not a port number).
    Duplicate object keys are rejected.

Nmap XML (``nmap -oX``), recognized by the root element ``<nmaprun>``.
    Parsed only with defusedxml, so entity declarations (billion laughs) and
    external references (XXE) are rejected. Mapping:

    * scanner: "nmap"
    * scan_type: the ``type`` of each ``<scaninfo>``, joined with "," (e.g.
      "syn,udp"); null if there is none
    * started_at: ``nmaprun/@start``; finished_at: ``runstats/finished/@time``
      (Unix epoch seconds, converted to UTC)
    * scan_id and target_range: null (Nmap does not record them reliably)
    * per ``<host>``:
        - ip: first ``<address>`` with addrtype ipv4 or ipv6 (MAC is skipped)
        - hostname: first ``<hostnames><hostname>/@name``
        - status: ``<status>/@state`` (anything other than up/down is "unknown")
        - os_guess: name of the ``<osmatch>`` with the highest accuracy (first
          one wins a tie)
        - ports: each ``<ports><port>``: @protocol, @portid, ``<state>/@state``,
          ``<service>`` @name/@product/@version. Nmap states outside the model
          (e.g. "closed|filtered", "unfiltered") become "unknown".
          ``<extraports>`` summaries are not individual ports and are skipped.
        - notes: each port ``<script>`` as "<portid>/<protocol> <script id>:
          <output>" in port order, then each ``<hostscript><script>`` as
          "<script id>: <output>"

After parsing, every non-note string field must be at most 512 characters,
and the result is passed through sanitizer.sanitize_scan.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from defusedxml import DefusedXmlException
from defusedxml.ElementTree import ParseError, fromstring
from pydantic import ValidationError

from recon_agent.models import ScanResult
from recon_agent.sanitizer import sanitize_scan

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

MAX_FIELD_CHARS = 512
_MAX_REPORTED_ERRORS = 5
_MODEL_PORT_STATES = frozenset({"open", "closed", "filtered", "open|filtered"})
_MODEL_HOST_STATES = frozenset({"up", "down"})


class ScanLoadError(Exception):
    """The scan file could not be loaded; the message says why."""


def load_scan(path: Path, *, max_bytes: int = 5_000_000) -> ScanResult:
    """Read, validate, and sanitize the scan file at `path`."""
    raw = _read_bytes(path, max_bytes)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ScanLoadError(
            f"{path.name}: file is not valid UTF-8 (bad byte at offset {exc.start})"
        ) from None

    stripped = text.lstrip()
    if not stripped:
        raise ScanLoadError(f"{path.name}: file is empty")
    if stripped.startswith(("{", "[")):
        scan = _parse_json(path.name, text)
    elif stripped.startswith("<"):
        scan = _parse_nmap_xml(path.name, raw)
    else:
        raise ScanLoadError(
            f"{path.name}: unknown format; expected a JSON object or Nmap XML (-oX) output"
        )

    _check_fields(path.name, scan)
    return sanitize_scan(scan)


def _read_bytes(path: Path, max_bytes: int) -> bytes:
    """Return the file contents after checking it exists, is a file, and is small enough."""
    if not path.exists():
        raise ScanLoadError(f"{path}: file not found")
    if not path.is_file():
        raise ScanLoadError(f"{path}: not a regular file")
    size = path.stat().st_size
    if size > max_bytes:
        raise ScanLoadError(f"{path.name}: file is {size} bytes, larger than the {max_bytes} limit")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ScanLoadError(f"{path.name}: could not read file ({exc.strerror})") from None
    if len(raw) > max_bytes:  # the file grew after the size check
        raise ScanLoadError(f"{path.name}: file is larger than the {max_bytes} byte limit")
    return raw


# --------------------------------------------------------------------------
# JSON
# --------------------------------------------------------------------------


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key {key[:40]!r}")
        result[key] = value
    return result


def _reject_constant(name: str) -> None:
    raise ValueError(f"{name} is not allowed")


def _parse_json(name: str, text: str) -> ScanResult:
    try:
        data = json.loads(
            text, object_pairs_hook=_reject_duplicate_keys, parse_constant=_reject_constant
        )
    except json.JSONDecodeError as exc:
        raise ScanLoadError(
            f"{name}: malformed JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})"
        ) from None
    except ValueError as exc:
        raise ScanLoadError(f"{name}: malformed JSON: {exc}") from None
    except RecursionError:
        raise ScanLoadError(f"{name}: malformed JSON: nested too deeply") from None
    if not isinstance(data, dict):
        raise ScanLoadError(f"{name}: top-level JSON value must be an object")
    try:
        return ScanResult.model_validate_json(text, strict=True)
    except ValidationError as exc:
        raise ScanLoadError(_describe_validation_error(name, exc)) from None


def _describe_validation_error(name: str, exc: ValidationError) -> str:
    """Summarize which fields failed, without echoing the offending values."""
    errors = exc.errors(include_input=False, include_url=False)
    lines = [f"{name}: scan data failed validation ({len(errors)} problem(s)):"]
    for error in errors[:_MAX_REPORTED_ERRORS]:
        lines.append(f"  {_format_loc(error['loc'])}: {error['msg'][:200]}")
    if len(errors) > _MAX_REPORTED_ERRORS:
        lines.append(f"  ... and {len(errors) - _MAX_REPORTED_ERRORS} more")
    return "\n".join(lines)


def _format_loc(loc: tuple[int | str, ...]) -> str:
    """Turn ('hosts', 0, 'ports', 1, 'port') into 'hosts[0].ports[1].port'."""
    path = ""
    for part in loc:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path += f".{part}" if path else str(part)
    return path or "(root)"


# --------------------------------------------------------------------------
# Nmap XML
# --------------------------------------------------------------------------


def _parse_nmap_xml(name: str, raw: bytes) -> ScanResult:
    try:
        root = fromstring(raw)
    except DefusedXmlException:
        raise ScanLoadError(
            f"{name}: XML uses entity declarations or external references, which are "
            "not allowed (possible XXE or entity-expansion attack)"
        ) from None
    except ParseError as exc:
        raise ScanLoadError(f"{name}: malformed XML: {exc}") from None
    if root.tag != "nmaprun":
        raise ScanLoadError(
            f"{name}: unknown format; XML root element is <{root.tag[:40]}>, "
            "expected Nmap <nmaprun>"
        )

    scan_types = [info.get("type") for info in root.findall("scaninfo") if info.get("type")]
    finished = root.find("runstats/finished")
    data = {
        "scan_id": None,
        "scanner": "nmap",
        "scan_type": ",".join(dict.fromkeys(scan_types)) or None,
        "started_at": _epoch(name, root.get("start"), "start time"),
        "finished_at": _epoch(
            name, finished.get("time") if finished is not None else None, "finished time"
        ),
        "target_range": None,
        "hosts": [_nmap_host(name, i, host) for i, host in enumerate(root.findall("host"))],
    }
    try:
        return ScanResult.model_validate(data)
    except ValidationError as exc:
        raise ScanLoadError(_describe_validation_error(name, exc)) from None


def _epoch(name: str, value: str | None, what: str) -> datetime | None:
    """Convert a Unix-epoch attribute to a UTC datetime (None if absent)."""
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=UTC)
    except (ValueError, OverflowError, OSError):
        raise ScanLoadError(f"{name}: Nmap {what} is not a valid Unix timestamp") from None


def _nmap_host(name: str, index: int, host: Element) -> dict[str, Any]:
    ip = next(
        (
            addr.get("addr")
            for addr in host.findall("address")
            if addr.get("addrtype") in ("ipv4", "ipv6")
        ),
        None,
    )
    if ip is None:
        raise ScanLoadError(f"{name}: Nmap host #{index} has no IPv4 or IPv6 address")

    hostname = host.find("hostnames/hostname")
    status = host.find("status")
    state = status.get("state") if status is not None else None

    ports: list[dict[str, Any]] = []
    notes: list[str] = []
    for port in host.findall("ports/port"):
        portid = port.get("portid", "")
        protocol = port.get("protocol", "")
        port_state = port.find("state")
        raw_state = port_state.get("state") if port_state is not None else None
        service = port.find("service")
        ports.append(
            {
                "port": portid,
                "protocol": protocol,
                "state": raw_state if raw_state in _MODEL_PORT_STATES else "unknown",
                "service": service.get("name") if service is not None else None,
                "product": service.get("product") if service is not None else None,
                "version": service.get("version") if service is not None else None,
            }
        )
        for script in port.findall("script"):
            notes.append(f"{portid}/{protocol} {script.get('id', '')}: {script.get('output', '')}")
    for script in host.findall("hostscript/script"):
        notes.append(f"{script.get('id', '')}: {script.get('output', '')}")

    return {
        "ip": ip,
        "hostname": hostname.get("name") if hostname is not None else None,
        "status": state if state in _MODEL_HOST_STATES else "unknown",
        "os_guess": _best_os_match(host),
        "ports": ports,
        "notes": notes,
    }


def _best_os_match(host: Element) -> str | None:
    """Return the name of the highest-accuracy <osmatch>; the first one wins a tie."""
    best_name: str | None = None
    best_accuracy = -1
    for match in host.findall("os/osmatch"):
        try:
            accuracy = int(match.get("accuracy", "0"))
        except ValueError:
            accuracy = 0
        if accuracy > best_accuracy:
            best_name, best_accuracy = match.get("name"), accuracy
    return best_name


# --------------------------------------------------------------------------
# Shared checks
# --------------------------------------------------------------------------


def _text_fields(scan: ScanResult) -> Iterator[tuple[str, str | None]]:
    """Yield (path, value) for every string field except notes."""
    for field in ("scan_id", "scanner", "scan_type", "target_range"):
        yield field, getattr(scan, field)
    for h, host in enumerate(scan.hosts):
        for field in ("ip", "hostname", "os_guess"):
            yield f"hosts[{h}].{field}", getattr(host, field)
        for p, port in enumerate(host.ports):
            for field in ("service", "product", "version"):
                yield f"hosts[{h}].ports[{p}].{field}", getattr(port, field)


def _check_fields(name: str, scan: ScanResult) -> None:
    """Reject oversized fields and IPv6 scope IDs (free text hidden inside an address)."""
    for path, value in _text_fields(scan):
        if value is not None and len(value) > MAX_FIELD_CHARS:
            raise ScanLoadError(
                f"{name}: {path} is {len(value)} characters long (limit {MAX_FIELD_CHARS})"
            )
    for h, host in enumerate(scan.hosts):
        if "%" in host.ip:
            raise ScanLoadError(f"{name}: hosts[{h}].ip has an IPv6 scope ID, which is not allowed")
