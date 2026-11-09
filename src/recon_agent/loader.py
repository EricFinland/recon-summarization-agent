"""Load and parse a synthetic scan-results file into a ScanResult."""

from pathlib import Path

from recon_agent.models import ScanResult


def load_scan(path: Path) -> ScanResult:
    """Read the scan file at `path` and return the parsed scan.

    TODO: decide supported input format(s) (JSON first) and implement.
    Raise a clear error on malformed input instead of guessing.
    """
    raise NotImplementedError
