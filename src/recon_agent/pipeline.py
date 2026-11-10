"""End-to-end flow: load -> summarize -> (narrate) -> validate -> write, with an audit trail."""

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, get_args

from recon_agent import __version__
from recon_agent.audit import append_audit_event, sha256_file
from recon_agent.config import Settings, load_settings
from recon_agent.loader import ScanLoadError, load_scan
from recon_agent.models import ObservationFlag, ReconSummary, ScanResult
from recon_agent.output import write_output
from recon_agent.summarizer import summarize
from recon_agent.validator import check_summary_text, validate_summary

# Writes overview.summary_text from a finished summary. May raise any Exception;
# the pipeline then keeps the template text.
Narrator = Callable[[ReconSummary], str]

_MAX_ERROR_CHARS = 300


class SummaryValidationError(Exception):
    """The summary did not pass validation; `problems` lists why."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = list(problems)
        super().__init__("Summary failed validation:\n- " + "\n- ".join(self.problems))


@dataclass
class RunResult:
    """Outcome of summarizing one scan file."""

    summary: ReconSummary
    output_path: Path | None
    narrator_used: bool
    warnings: list[str] = field(default_factory=list)


def _describe_error(exc: BaseException) -> str:
    """Return a short, single-line description of `exc`."""
    message = " ".join(str(exc).split())
    if len(message) > _MAX_ERROR_CHARS:
        message = message[:_MAX_ERROR_CHARS] + "..."
    return f"{type(exc).__name__}: {message}" if message else type(exc).__name__


def _draft(scan: ScanResult, scan_file: str, narrator: Narrator | None) -> RunResult:
    """Summarize `scan` and, if a narrator is given and its text is grounded, use its text."""
    summary = summarize(scan, scan_file)
    result = RunResult(summary=summary, output_path=None, narrator_used=False)
    if narrator is None:
        return result
    try:
        text = narrator(summary.model_copy(deep=True))  # the narrator cannot alter the facts
    except Exception as exc:  # a narrator failure must never fail the run
        result.warnings.append(f"narrator failed ({_describe_error(exc)}); kept template text")
        return result
    if not isinstance(text, str):
        result.warnings.append(
            f"narrator returned {type(text).__name__}, not text; kept template text"
        )
        return result
    text = text.strip()
    problems = check_summary_text(text, scan)
    if problems:
        result.warnings.append(
            "narrator text rejected (" + "; ".join(problems) + "); kept template text"
        )
        return result
    summary.overview.summary_text = text
    result.narrator_used = True
    return result


def summarize_file(
    input_path: Path,
    *,
    settings: Settings | None = None,
    narrator: Narrator | None = None,
) -> RunResult:
    """Load, summarize, and validate one scan file without writing anything.

    Raises ScanLoadError if the file cannot be loaded and SummaryValidationError
    if the summary is not fully supported by the input.
    """
    settings = settings or load_settings()
    scan = load_scan(input_path, max_bytes=settings.max_input_bytes)
    result = _draft(scan, input_path.name, narrator)
    problems = validate_summary(result.summary, scan)
    if problems:
        raise SummaryValidationError(problems)
    return result


def _flag_counts(summary: ReconSummary) -> dict[str, int]:
    """Count observations by flag, with every known flag present."""
    counts = Counter(
        flag for host in summary.hosts for obs in host.observations for flag in obs.flags
    )
    return {flag: counts[flag] for flag in get_args(ObservationFlag)}


def run(
    input_path: Path,
    output_dir: Path | None = None,
    *,
    settings: Settings | None = None,
    narrator: Narrator | None = None,
) -> RunResult:
    """Summarize one scan file, write the summary, and append one audit event.

    The audit event is written whether the run succeeds or fails; failures are
    re-raised after logging.
    """
    settings = settings or load_settings()
    output_dir = output_dir if output_dir is not None else settings.output_dir
    event: dict[str, Any] = {
        "step": "recon_summarize",
        "agent_version": __version__,
        "input_file": str(input_path),
        "input_sha256": None,
        "outcome": "error",
        "problems": [],
        "warnings": [],
        "narrator_configured": narrator is not None,
        "narrator_used": False,
        "summary_text_source": "template",
        "flagged_note_counts": None,
        "hosts_total": None,
        "open_ports_total": None,
        "output_path": None,
    }
    try:
        event["input_sha256"] = sha256_file(input_path)
    except OSError:
        pass

    try:
        try:
            scan = load_scan(input_path, max_bytes=settings.max_input_bytes)
        except (ScanLoadError, OSError) as exc:
            event["outcome"] = "load_error"
            event["problems"] = [_describe_error(exc)]
            raise
        result = _draft(scan, input_path.name, narrator)
        summary = result.summary
        event.update(
            warnings=result.warnings,
            narrator_used=result.narrator_used,
            summary_text_source="narrator" if result.narrator_used else "template",
            flagged_note_counts=_flag_counts(summary),
            hosts_total=summary.overview.hosts_total,
            open_ports_total=summary.overview.open_ports_total,
        )
        problems = validate_summary(summary, scan)
        if problems:
            event["outcome"] = "validation_error"
            event["problems"] = problems
            raise SummaryValidationError(problems)
        result.output_path = write_output(summary, output_dir, scan_file=input_path.name)
        event["output_path"] = str(result.output_path)
        event["outcome"] = "ok"
        return result
    except Exception as exc:
        if event["outcome"] == "error":
            event["problems"] = [_describe_error(exc)]
        raise
    finally:
        append_audit_event(settings.audit_log_path, event)
