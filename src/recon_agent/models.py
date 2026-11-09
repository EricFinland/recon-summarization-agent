"""Data models for parsed scan input and the structured summary output.

ReconSummary must stay in sync with schemas/recon_summary.schema.json, since
that schema is the contract with Group 2's classification agent.
"""

from pydantic import BaseModel


class ScanResult(BaseModel):
    """Parsed scan-results input (see data/scans/sample_scan_01.json).

    TODO: add fields (scan_id, target_range, hosts, ports, notes, ...).
    """


class ReconSummary(BaseModel):
    """Structured summary handed to Group 2.

    TODO: add fields matching schemas/recon_summary.schema.json.
    """
