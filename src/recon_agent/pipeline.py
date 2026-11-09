"""End-to-end flow: load -> summarize -> validate -> write."""

from pathlib import Path

from recon_agent.loader import load_scan
from recon_agent.output import write_output
from recon_agent.summarizer import summarize
from recon_agent.validator import validate_summary


def run(input_path: Path, output_dir: Path) -> Path:
    """Summarize one scan file and return the path of the written summary."""
    scan = load_scan(input_path)
    summary = summarize(scan, scan_file=input_path.name)
    problems = validate_summary(summary, scan)
    if problems:
        raise ValueError("Summary failed validation:\n- " + "\n- ".join(problems))
    return write_output(summary, output_dir, scan_file=input_path.name)
