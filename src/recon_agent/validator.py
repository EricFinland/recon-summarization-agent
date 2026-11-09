"""Check a summary against the source scan data and the output schema."""

from recon_agent.models import ReconSummary, ScanResult


def validate_summary(summary: ReconSummary, scan: ScanResult) -> list[str]:
    """Return a list of problems (an empty list means the summary is valid).

    TODO:
    - validate against schemas/recon_summary.schema.json
    - every host, port, service, product, and version exists in the input
    - every observation's `evidence` path resolves to a real input field
    - overview counts match the input
    """
    raise NotImplementedError
