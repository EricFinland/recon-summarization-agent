"""Summarize parsed scan data into a ReconSummary.

Rule: only report what is present in the scan input. Hosts, ports, counts, and
observations are copied deterministically from the input. The only free text
is overview.summary_text, which defaults to template_summary_text() and may be
replaced by a narrator only after it passes the grounding check.
"""

from datetime import UTC, datetime

from recon_agent.models import (
    HostSummary,
    Observation,
    OpenPort,
    OtherPort,
    Overview,
    ReconSummary,
    ScanHost,
    ScanResult,
    SourceInfo,
)
from recon_agent.sanitizer import check_note


def summarize(
    scan: ScanResult, scan_file: str, *, generated_at: datetime | None = None
) -> ReconSummary:
    """Build the structured summary for `scan`, read from the file named `scan_file`."""
    if generated_at is None:
        generated_at = datetime.now(UTC)
    elif generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=UTC)

    hosts = [_summarize_host(index, host) for index, host in enumerate(scan.hosts)]
    summary = ReconSummary(
        generated_at=generated_at,
        source=SourceInfo(
            scan_file=scan_file, scan_id=scan.scan_id, target_range=scan.target_range
        ),
        overview=Overview(
            hosts_total=len(hosts),
            hosts_up=sum(host.status == "up" for host in hosts),
            open_ports_total=sum(len(host.open_ports) for host in hosts),
            summary_text="",
        ),
        hosts=hosts,
    )
    summary.overview.summary_text = template_summary_text(summary)
    return summary


def _summarize_host(index: int, host: ScanHost) -> HostSummary:
    """Copy one input host into its summary form."""
    open_ports = [
        OpenPort(
            port=p.port,
            protocol=p.protocol,
            service=p.service,
            product=p.product,
            version=p.version,
        )
        for p in host.ports
        if p.state == "open"
    ]
    other_ports = [
        OtherPort(port=p.port, protocol=p.protocol, state=p.state, service=p.service)
        for p in host.ports
        if p.state != "open"
    ]
    observations = []
    for note_index, note in enumerate(host.notes):
        if not note.strip():
            continue
        check = check_note(note)
        observations.append(
            Observation(
                text=check.text,
                evidence=f"hosts[{index}].notes[{note_index}]",
                flags=list(check.flags),
            )
        )
    return HostSummary(
        ip=host.ip,
        hostname=host.hostname,
        status=host.status,
        os_guess=host.os_guess,
        open_ports=open_ports,
        other_ports=other_ports,
        observations=observations,
    )


_STATUS_LABELS = {"up": "up", "down": "down", "unknown": "with unknown status"}


def _count(n: int, noun: str) -> str:
    """Return e.g. '1 host' or '3 hosts'."""
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def template_summary_text(summary: ReconSummary) -> str:
    """Return a deterministic plain-language overview built only from `summary`."""
    hosts = summary.hosts
    scope = f" in {summary.source.target_range}" if summary.source.target_range else ""
    if not hosts:
        return f"The scan lists no hosts{scope}."

    statuses = [host.status for host in hosts]
    status_parts = [
        f"{statuses.count(status)} {label}"
        for status, label in _STATUS_LABELS.items()
        if status in statuses
    ]
    sentences = [f"{_count(len(hosts), 'host')} listed{scope}: {', '.join(status_parts)}."]

    open_ports = [port for host in hosts for port in host.open_ports]
    if open_ports:
        hosts_with_open = sum(bool(host.open_ports) for host in hosts)
        sentences.append(
            f"{_count(len(open_ports), 'open port')} across {_count(hosts_with_open, 'host')}."
        )
        services = list(dict.fromkeys(p.service for p in open_ports if p.service))
        if services:
            sentences.append(f"Open services: {', '.join(services)}.")
        unnamed = sum(p.service is None for p in open_ports)
        if unnamed:
            sentences.append(f"Open ports without a service name: {unnamed}.")
        idle_up = sum(host.status == "up" and not host.open_ports for host in hosts)
        if idle_up:
            sentences.append(f"Up hosts with no open ports: {idle_up}.")
    else:
        sentences.append("No open ports were reported.")

    other_total = sum(len(host.other_ports) for host in hosts)
    if other_total:
        sentences.append(f"Ports not in the open state: {other_total}.")

    observations = [obs for host in hosts for obs in host.observations]
    if observations:
        sentences.append(f"{_count(len(observations), 'observation')} recorded from scan notes.")
    withheld = sum("possible_prompt_injection" in obs.flags for obs in observations)
    if withheld:
        sentences.append(f"Notes withheld because of instruction-like text: {withheld}.")
    truncated = sum("truncated" in obs.flags for obs in observations)
    if truncated:
        sentences.append(f"Notes truncated to the maximum length: {truncated}.")
    return " ".join(sentences)
