"""Aggregate facts about a summary, shared by the narrator and the grounding check.

`summary_text` is an aggregate overview: it describes the scan as a whole and
never names individual hosts (host-level detail lives in `hosts[]`). The same
aggregate facts are what the LLM narrator is allowed to see (`llm.build_facts`)
and the only numbers narrative text may state (`validator.check_summary_text`).
No IP addresses or hostnames appear here.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Iterator
from typing import Any

from recon_agent.models import ReconSummary


def _counts(values: Iterable[str | None]) -> dict[str, int]:
    """Count non-empty values, keeping first-seen order."""
    return dict(Counter(value for value in values if value))


def aggregate_facts(summary: ReconSummary) -> dict[str, Any]:
    """Return scan-wide counts and distinct values; nothing that identifies a host."""
    hosts = summary.hosts
    open_ports = [port for host in hosts for port in host.open_ports]
    flags = [flag for host in hosts for obs in host.observations for flag in obs.flags]
    statuses = Counter(host.status for host in hosts)
    return {
        "target_range": summary.source.target_range,
        "hosts_total": len(hosts),
        "hosts_up": statuses["up"],
        "hosts_down": statuses["down"],
        "hosts_unknown": statuses["unknown"],
        "open_ports_total": len(open_ports),
        "hosts_with_open_ports": sum(bool(host.open_ports) for host in hosts),
        "hosts_up_without_open_ports": sum(
            host.status == "up" and not host.open_ports for host in hosts
        ),
        "open_ports_without_service": sum(port.service is None for port in open_ports),
        "ports_not_open_total": sum(len(host.other_ports) for host in hosts),
        "observations_total": sum(len(host.observations) for host in hosts),
        "notes_withheld": flags.count("possible_prompt_injection"),
        "notes_truncated": flags.count("truncated"),
        "open_services": _counts(port.service for port in open_ports),
        "open_products": _counts(
            " ".join(part for part in (port.product, port.version) if part) or None
            for port in open_ports
        ),
        "os_guesses": _counts(host.os_guess for host in hosts),
    }


def fact_numbers(facts: Any) -> set[int]:
    """Return every integer value nested anywhere in `facts` (bools excluded)."""
    if isinstance(facts, bool):
        return set()
    if isinstance(facts, int):
        return {facts}
    if isinstance(facts, dict):
        return set().union(*(fact_numbers(value) for value in facts.values()))
    if isinstance(facts, list):
        return set().union(*(fact_numbers(value) for value in facts))
    return set()


def fact_strings(facts: Any) -> Iterator[str]:
    """Yield every string nested anywhere in `facts`, dict keys included."""
    if isinstance(facts, str):
        yield facts
    elif isinstance(facts, dict):
        for key, value in facts.items():
            yield from fact_strings(key)
            yield from fact_strings(value)
    elif isinstance(facts, list):
        for item in facts:
            yield from fact_strings(item)
