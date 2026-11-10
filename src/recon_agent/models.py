"""Data models for parsed scan input and the structured summary output.

These models are the internal contract between the agent's modules:

    loader.py     produces  ScanResult
    summarizer.py turns     ScanResult -> ReconSummary
    validator.py  checks    ReconSummary against ScanResult
    output.py     writes    ReconSummary as JSON

ReconSummary must stay in sync with schemas/recon_summary.schema.json, since
that schema is the contract with Group 2's classification agent.
"""

from __future__ import annotations

import ipaddress
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = "0.2.0"

Protocol = Literal["tcp", "udp"]
PortState = Literal["open", "closed", "filtered", "open|filtered", "unknown"]
HostStatus = Literal["up", "down", "unknown"]
ObservationFlag = Literal["possible_prompt_injection", "truncated"]

# Text used in place of a scan note that was withheld because it looked like
# instructions aimed at an AI model (prompt injection).
WITHHELD_NOTE_TEXT = (
    "Note withheld from summary: it contains instruction-like text. "
    "Review the raw scan file at the evidence path."
)


def _check_ip(value: str) -> str:
    ipaddress.ip_address(value)  # raises ValueError if not a valid IPv4/IPv6 address
    return value


# --------------------------------------------------------------------------
# Input: parsed scan results
# --------------------------------------------------------------------------


class ScanPort(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    port: int = Field(ge=0, le=65535)
    protocol: Protocol
    state: PortState
    service: str | None = None
    product: str | None = None
    version: str | None = None


class ScanHost(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    ip: str
    hostname: str | None = None
    status: HostStatus = "unknown"
    os_guess: str | None = None
    ports: list[ScanPort] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @field_validator("ip")
    @classmethod
    def validate_ip(cls, value: str) -> str:
        return _check_ip(value)


class ScanResult(BaseModel):
    """Parsed scan-results input (see data/scans/)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    scan_id: str | None = None
    scanner: str | None = None
    scan_type: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    target_range: str | None = None
    hosts: list[ScanHost] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Output: structured summary for Group 2
# --------------------------------------------------------------------------


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceInfo(_Out):
    scan_file: str
    scan_id: str | None
    target_range: str | None = None


class Overview(_Out):
    hosts_total: int = Field(ge=0)
    hosts_up: int = Field(ge=0)
    open_ports_total: int = Field(ge=0)
    summary_text: str


class OpenPort(_Out):
    port: int = Field(ge=0, le=65535)
    protocol: Protocol
    service: str | None
    product: str | None
    version: str | None


class OtherPort(_Out):
    port: int = Field(ge=0, le=65535)
    protocol: Protocol
    state: Literal["closed", "filtered", "open|filtered", "unknown"]
    service: str | None


class Observation(_Out):
    text: str
    evidence: str = Field(description="Path into the input, e.g. 'hosts[0].notes[1]'.")
    flags: list[ObservationFlag] = Field(default_factory=list)


class HostSummary(_Out):
    ip: str
    hostname: str | None
    status: HostStatus
    os_guess: str | None
    open_ports: list[OpenPort]
    other_ports: list[OtherPort]
    observations: list[Observation]


class ReconSummary(_Out):
    """Structured summary handed to Group 2."""

    schema_version: Literal["0.2.0"] = SCHEMA_VERSION
    generated_at: datetime
    source: SourceInfo
    overview: Overview
    hosts: list[HostSummary]
