"""Write the structured summary to disk for Group 2 to consume."""

from pathlib import Path

from recon_agent.models import ReconSummary


def write_output(summary: ReconSummary, output_dir: Path, scan_file: str) -> Path:
    """Write `summary` as JSON into `output_dir` and return the file path.

    TODO: name the file `<scan_file stem>.summary.json` (matching
    schemas/examples/), pretty-printed, UTF-8.
    """
    raise NotImplementedError
