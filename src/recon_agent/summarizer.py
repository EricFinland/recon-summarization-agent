"""Summarize parsed scan data into a ReconSummary.

Rule: only report what is present in the scan input. Do not add hosts,
ports, services, versions, OS guesses, or findings the input does not support.
"""

from recon_agent.models import ReconSummary, ScanResult


def summarize(scan: ScanResult, scan_file: str) -> ReconSummary:
    """Build the structured summary for `scan`.

    TODO: copy deterministic parts (hosts, ports, counts) straight from the
    input. Use the LLM only for summary_text and for rewording notes into
    observations.
    """
    raise NotImplementedError
